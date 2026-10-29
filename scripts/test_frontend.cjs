// Verify registration and authentication without touching live accounts.
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const { test } = require('node:test');
const source = readFileSync(resolve(__dirname, '../portal/static/portal/university.js'), 'utf8');

function harness(responses = []) {
  const handlers = {}, nodes = new Map(), storage = new Map(), requests = [], exports = [];
  const app = { innerHTML: '', addEventListener: (type, handler) => { handlers[type] = handler; } };
  const document = {
    title: '',
    createElement() { return {click(){}}; },
    querySelector(selector) {
      if (selector === '#app') return app;
      if (!nodes.has(selector)) nodes.set(selector, {innerHTML:'',textContent:'',focus(){},scrollIntoView(){},isConnected:true});
      return nodes.get(selector);
    },
  };
  const context = vm.createContext({
    document, console, Blob, setTimeout: callback => callback(),
    URL: {createObjectURL: blob => { exports.push(blob); return 'blob:test'; }, revokeObjectURL(){}},
    sessionStorage: {getItem: key => storage.get(key) || null, setItem:(key,value) => storage.set(key,value), removeItem:key => storage.delete(key)},
    FormData: class { constructor(form) { return Object.entries(form.fields); } },
    fetch: async (url, options) => {
      requests.push({url, options});
      const item = responses.shift();
      assert.ok(item, `Unexpected request: ${url}`);
      return {ok: item.status < 400,status:item.status,text:async () => JSON.stringify(item.data)};
    },
  });
  vm.runInContext(source, context);
  async function submit(fields, mode = 'register') {
    vm.runInContext(`authMode = '${mode}'; renderAuth();`, context);
    const button = {disabled:false,isConnected:true};
    await handlers.submit({preventDefault(){},target:{id:'auth-form',fields,querySelector:() => button}});
  }
  return {app,nodes,storage,requests,submit,context,exports,handlers};
}

test('registration sends admission number and returns to login without storing the returned token', async () => {
  const h = harness([{status:201,data:{token:'signup-token',expires_at:'2099-01-01T00:00:00Z',user:{username:'newstudent',role:'STUDENT',admission_number:'DU/26/007'}}}]);
  await h.submit({username:'newstudent',password:'Sample!482',confirm_password:'Sample!482',email:'test@example.com',admission_number:'DU/26/007'});
  assert.deepEqual(h.requests.map(item => item.url), ['/api/register/']);
  assert.equal(JSON.parse(h.requests[0].options.body).confirm_password, undefined);
  assert.equal(JSON.parse(h.requests[0].options.body).admission_number, 'DU/26/007');
  assert.match(h.app.innerHTML, /Your account has been created/);
  assert.match(h.app.innerHTML, /Sign in to portal/);
  assert.match(h.app.innerHTML, /value="newstudent"/);
  assert.doesNotMatch(h.app.innerHTML, /id="confirm_password"/);
  assert.equal(h.storage.size, 0);
});
test('mismatched passwords do not submit registration', async () => {
  const h = harness();
  await h.submit({username:'student',password:'One!',confirm_password:'Two!'});
  assert.equal(h.requests.length, 0);
  assert.match(h.nodes.get('#auth-feedback').innerHTML, /passwords do not match/);
});
test('rejected registration stays on registration and displays validation', async () => {
  const h = harness([{status:400,data:{username:['A user with that username already exists.']}}]);
  await h.submit({username:'student',password:'Sample!482',confirm_password:'Sample!482'});
  assert.match(h.nodes.get('#auth-feedback').innerHTML, /already exists/);
  assert.match(h.app.innerHTML, /id="confirm_password"/);
  assert.equal(h.storage.size, 0);
});
test('explicit login sends the returned token when loading student results', async () => {
  const h = harness([
    {status:200,data:{username:'student',role:'STUDENT',token:'test-token'}},
    {status:200,data:[]},
    {status:200,data:{id:3,name:'Student',current_class_name:'Year 1 A'}},
  ]);
  await h.submit({username:'student',password:'Sample!482'}, 'login');
  assert.deepEqual(h.requests.map(item => item.url), ['/api/login/','/api/student/grades/','/api/student/profile/']);
  assert.equal(h.requests[1].options.headers.Authorization, 'Token test-token');
  assert.match(h.nodes.get('#dashboard-content').innerHTML, /Your results will appear here/);
  assert.match(h.nodes.get('#dashboard-content').innerHTML, /Year 1 A/);
  assert.doesNotMatch(h.app.innerHTML + h.nodes.get('#dashboard-content').innerHTML, /API index|Django|backend|profile ID/);
});
test('expired credentials return to login and clear the saved token', async () => {
  const h = harness([
    {status:200,data:{username:'student',role:'STUDENT',token:'expired'}},
    {status:401,data:{detail:'Invalid token.'}},
    {status:401,data:{detail:'Invalid token.'}},
  ]);
  await h.submit({username:'student',password:'Sample!482'}, 'login');
  assert.match(h.app.innerHTML, /Your session has ended/);
  assert.equal(h.storage.size, 0);
});

test('admin class form creates a class and refreshes the directory', async () => {
  const initial = [
    {status:200,data:{total_students:1,total_teachers:1,total_subjects:1}},
    {status:200,data:[]},
    {status:200,data:[{id:5,name:'Ada Okafor',username:'lecturer'}]},
    {status:200,data:[{id:3,name:'Tomi Bello',username:'student',current_class:null}]},
  ];
  const updated = [
    {status:200,data:{id:7,name:'Year 1 A',class_teacher:5}},
    {status:200,data:{total_students:1,total_teachers:1,total_subjects:1}},
    {status:200,data:[{id:7,name:'Year 1 A',class_teacher:5,teacher_name:'Ada Okafor',student_count:0}]},
    {status:200,data:[{id:5,name:'Ada Okafor',username:'lecturer'}]},
    {status:200,data:[{id:3,name:'Tomi Bello',username:'student',current_class:null}]},
  ];
  const h = harness([{status:200,data:{username:'admin',role:'ADMIN',token:'admin-token'}},...initial,...updated]);
  await h.submit({username:'admin',password:'Sample!482'}, 'login');
  assert.match(h.nodes.get('#dashboard-content').innerHTML, /Create a class/);
  const button = {disabled:false,isConnected:true};
  await h.handlers.submit({preventDefault(){},target:{id:'create-class-form',fields:{name:'Year 1 A',class_teacher:'5'},querySelector:() => button}});
  assert.equal(h.requests[5].url, '/api/admin/classes/');
  assert.deepEqual(JSON.parse(h.requests[5].options.body), {name:'Year 1 A',class_teacher:5});
  assert.match(h.nodes.get('#dashboard-content').innerHTML, /Year 1 A/);
  assert.match(h.nodes.get('#dashboard-content').innerHTML, /Class Year 1 A created/);
});

test('lecturer sees recorded results and the list refreshes after saving', async () => {
  const savedGrade = {student_name:'Tomi Bello',subject_name:'Mathematics',session_name:'2026/2027',continous_assessment_score:'20.00',exam_score:'50.00',total_score:'70.00'};
  const h = harness([
    {status:200,data:{username:'lecturer',role:'TEACHER',token:'teacher-token'}},
    {status:200,data:[{id:4,name:'Mathematics',code:'MATH101'}]},
    {status:200,data:[{id:3,name:'Tomi Bello',username:'student'}]},
    {status:200,data:[]},
    {status:200,data:[]},
    {status:201,data:savedGrade},
    {status:200,data:[savedGrade]},
  ]);
  await h.submit({username:'lecturer',password:'Sample!482'}, 'login');
  assert.match(h.nodes.get('#dashboard-content').innerHTML, /No results recorded yet/);
  const button = {disabled:false,isConnected:true};
  let reset = false;
  await h.handlers.submit({preventDefault(){},target:{id:'grade-form',fields:{subject:'4',student:'3',ca:'20',exam:'50'},isConnected:true,reset(){reset=true;},querySelector:() => button}});
  assert.equal(h.requests[5].url, '/api/teacher/grades/record/4/');
  assert.equal(h.requests[6].url, '/api/teacher/grades/');
  assert.equal(h.requests[6].options.headers.Authorization, 'Token teacher-token');
  assert.equal(reset, true);
  assert.match(h.nodes.get('#recorded-results-content').innerHTML, /Tomi Bello/);
  assert.match(h.nodes.get('#recorded-results-content').innerHTML, /70.00/);
  assert.match(h.nodes.get('#action-feedback').innerHTML, /Result saved successfully/);
});

test('result export follows the selected session and escapes spreadsheet formulas', async () => {
  const h = harness();
  vm.runInContext(`
    allGrades = [
      {session:1, subject_name:'Other result',session_name:'2025/2026',total_score:80},
      {session:2, subject_name:'=1+1',session_name:'2026/2027',continous_assessment_score:30,exam_score:50,total_score:80}
    ];
    selectedSession = '2';
    downloadResults();
  `, h.context);
  assert.equal(h.exports.length, 1);
  const csv = await h.exports[0].text();
  assert.doesNotMatch(csv, /Other result/);
  assert.match(csv, /"'=1\+1"/);
  assert.match(csv, /"2026\/2027","30","50","80"/);
});
