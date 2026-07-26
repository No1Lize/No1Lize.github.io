import assert from "node:assert/strict";
import test from "node:test";
import {
  companyDatabaseLinks,
  personDatabaseLinks,
} from "../lib/external-database-links";

test("chinese companies get qcc and jingdata entry links", () => {
  const links = companyDatabaseLinks("智元机器人", "中国");
  assert.equal(links.length, 2);
  const [qcc, jingdata] = links;
  assert.equal(qcc.platform, "企查查");
  assert.equal(
    qcc.url,
    `https://www.qcc.com/web/search?key=${encodeURIComponent("智元机器人")}`,
  );
  assert.equal(jingdata.platform, "鲸准");
  assert.ok(jingdata.url.startsWith("https://www.bing.com/search?q="));
  assert.ok(
    decodeURIComponent(jingdata.url).includes('site:jingdata.com "智元机器人"'),
  );
});

test("overseas companies and empty names produce no registry links", () => {
  assert.equal(companyDatabaseLinks("OpenAI", "美国").length, 0);
  assert.equal(companyDatabaseLinks("   ").length, 0);
});

test("company names are whitespace-normalized before building urls", () => {
  const [qcc] = companyDatabaseLinks("宁德  时代", "中国");
  assert.equal(
    qcc.url,
    `https://www.qcc.com/web/search?key=${encodeURIComponent("宁德 时代")}`,
  );
});

test("person links require a chinese name", () => {
  assert.equal(personDatabaseLinks("Warren Buffett").length, 0);
  const links = personDatabaseLinks("段永平");
  assert.equal(links.length, 2);
  assert.ok(links[0].url.includes(encodeURIComponent("段永平")));
  assert.ok(links.every((link) => link.url.startsWith("https://")));
});
