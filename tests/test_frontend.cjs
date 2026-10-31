const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const C = require("../src/static/core.js");

test("stale query and profile responses cannot win a request gate", () => {
  const gate = C.gate();
  const first = gate.next(),
    second = gate.next();
  assert.equal(gate.valid(first), false);
  assert.equal(gate.valid(second), true);
  gate.cancel();
  assert.equal(gate.valid(second), false);
});
test("external songs with the same missing row retain distinct identities", () => {
  const a = { row: -1, name: "One", artist: "Artist" },
    b = { row: -1, name: "Two", artist: "Artist" };
  assert.notEqual(C.key(a), C.key(b));
  assert.equal(C.unique([a, b, a]).length, 2);
});
test("catalog row zero is a valid identity", () => {
  assert.equal(
    C.unique([{ row: 0, name: "Song", artist: "Artist" }])[0].row,
    0,
  );
});
test("feedback belongs to song identity, not a reused row number", () => {
  const a = { row: -1, name: "One", artist: "Artist" },
    b = { row: -1, name: "Two", artist: "Artist" };
  assert.equal(C.signal([{ ...a, signal: "like" }], b), "none");
  assert.equal(C.signal([{ ...a, signal: "like" }], a), "like");
});
test("text is escaped before being placed in markup", () => {
  assert.equal(
    C.escape("<img src=\"x\" onerror='bad'>"),
    "&lt;img src=&quot;x&quot; onerror=&#39;bad&#39;&gt;",
  );
});
test("provider links reject script and unrelated destinations", () => {
  assert.equal(C.safeUrl("javascript:alert(1)"), "");
  assert.equal(C.safeUrl("https://unrelated.example/path"), "");
  assert.match(C.safeUrl("https://music.apple.com/us/song/123"), /^https:/);
});
test("preview times handle nonfinite and zero input without invented progress", () => {
  assert.equal(C.time(Infinity), "0:00");
  assert.equal(C.time(0), "0:00");
  assert.equal(C.time(undefined), "0:00");
  assert.equal(C.time(30), "0:30");
  assert.equal(C.time(75), "1:15");
});
test("the shell has no manual taste setup or artist genre classification badges", () => {
  const source = fs.readFileSync(
    path.join(__dirname, "../src/static/script.js"),
    "utf8",
  );
  assert.doesNotMatch(
    source,
    /homePreferencesForm|preferredLanguages|preferredArtists|genre-badge|score-badge/,
  );
  assert.doesNotMatch(source, />\s*Like\s*</);
  assert.match(source, /aria-pressed/);
});

test("reloading a song route cannot select a different cached song with the same temporary ID", () => {
  const params = {
    id: "1",
    name: "Chosen Song",
    artist: "Chosen Artist",
    row: "0",
  };
  const cached = { row: 5, name: "A Different Song", artist: "Another Artist" };
  assert.deepEqual(C.selectedTrack(params, cached), {
    name: "Chosen Song",
    artist: "Chosen Artist",
    row: 0,
  });
});
test("a song URL remains useful without any in-memory registry", () => {
  assert.deepEqual(
    C.selectedTrack({ name: "Live Song", artist: "Artist", row: "-1" }, null),
    { name: "Live Song", artist: "Artist", row: -1 },
  );
});
test("a temporary ID alone is never accepted as a song identity", () => {
  assert.equal(
    C.selectedTrack(
      { id: "1" },
      { name: "Wrong Song", artist: "Wrong Artist" },
    ),
    null,
  );
});

test('the static deployment serves every local script used by the app shell',()=>{
    const config=JSON.parse(fs.readFileSync(path.join(__dirname,'../src/vercel.json'),'utf8'));
    for(const asset of ['/core.js','/script.js','/style.css']){
        const route=config.routes.find(route=>route.src===asset);
        assert.ok(route,`${asset} must not fall through to index.html`);
        assert.ok(fs.existsSync(path.join(__dirname,'../src',route.dest)));
    }
});
test('an unconfigured API proxy returns a usable service error instead of throwing',async()=>{
    const source=fs.readFileSync(path.join(__dirname,'../src/api/[...path].js'),'utf8');
    const {default:handler}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
    const names=['SOUNDVECTOR_API_BASE','HF_SPACE_URL','NEXT_PUBLIC_HF_SPACE_URL'];
    const previous=Object.fromEntries(names.map(name=>[name,process.env[name]]));
    names.forEach(name=>delete process.env[name]);
    const result={status:null,data:null};
    const response={status(code){result.status=code;return this;},json(data){result.data=data;return this;}};
    try{await handler({query:{path:'home'},url:'/api/home'},response);assert.equal(result.status,503);assert.match(result.data.detail,/music service/);}
    finally{names.forEach(name=>{if(previous[name]===undefined)delete process.env[name];else process.env[name]=previous[name];});}
});
