import fs from "node:fs";
import path from "node:path";
import ts from "typescript";

const sourceRoot = path.resolve("src");
const localePath = path.join(sourceRoot, "i18n.tsx");
const localeText = fs.readFileSync(localePath, "utf8");
const localeSource = ts.createSourceFile(
  localePath,
  localeText,
  ts.ScriptTarget.Latest,
  true,
  ts.ScriptKind.TSX,
);
const translations = new Set();
const sources = new Set();
const translatableAttributes = new Set([
  "aria-label",
  "title",
  "placeholder",
  "label",
  "hint",
  "description",
  "eyebrow",
  "fallback",
  "empty",
  "message",
  "confirm",
  "cancel",
  "close",
  "submitLabel",
]);
const translatableProperties = new Set([
  "label",
  "title",
  "description",
  "eyebrow",
  "hint",
  "placeholder",
  "empty",
  "confirm",
  "cancel",
  "close",
  "message",
  "steps",
]);

function normalizeJsxText(raw) {
  const lines = raw.replace(/\r/g, "").split("\n");
  let result = "";
  for (let index = 0; index < lines.length; index += 1) {
    let line = lines[index].replace(/\t/g, " ");
    if (index > 0) line = line.replace(/^\s+/, "");
    if (index < lines.length - 1) line = line.replace(/\s+$/, "");
    if (line) result += `${index > 0 && result ? " " : ""}${line}`;
  }
  return result;
}

function readTranslations(node) {
  if (ts.isVariableDeclaration(node) && node.initializer) {
    const name = node.name.getText(localeSource);
    if (
      ["EN", "EN_EXTRA"].includes(name) &&
      ts.isObjectLiteralExpression(node.initializer)
    ) {
      for (const property of node.initializer.properties)
        if (
          ts.isPropertyAssignment(property) &&
          ts.isStringLiteral(property.name)
        )
          translations.add(property.name.text);
    }
  }
  if (ts.isCallExpression(node) && node.expression.getText(localeSource) === "Object.assign") {
    const target = node.arguments[0]?.getText(localeSource);
    const entries = node.arguments[1];
    if (
      target === "EN_EXTRA" &&
      entries &&
      ts.isCallExpression(entries) &&
      entries.expression.getText(localeSource) === "Object.fromEntries" &&
      ts.isArrayLiteralExpression(entries.arguments[0])
    )
      for (const tuple of entries.arguments[0].elements)
        if (
          ts.isArrayLiteralExpression(tuple) &&
          ts.isStringLiteral(tuple.elements[0])
        )
          translations.add(tuple.elements[0].text);
  }
  ts.forEachChild(node, readTranslations);
}
readTranslations(localeSource);

function addStaticStringLiterals(node) {
  if (ts.isStringLiteral(node)) sources.add(node.text);
  else ts.forEachChild(node, addStaticStringLiterals);
}

function addResultStrings(node) {
  if (ts.isParenthesizedExpression(node)) {
    addResultStrings(node.expression);
  } else if (ts.isConditionalExpression(node)) {
    addResultStrings(node.whenTrue);
    addResultStrings(node.whenFalse);
  } else if (
    ts.isBinaryExpression(node) &&
    [
      ts.SyntaxKind.AmpersandAmpersandToken,
      ts.SyntaxKind.BarBarToken,
      ts.SyntaxKind.QuestionQuestionToken,
    ].includes(node.operatorToken.kind)
  ) {
    addResultStrings(node.right);
  } else if (ts.isStringLiteral(node)) {
    sources.add(node.text);
  }
}

function inspectDirectory(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const filename = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      inspectDirectory(filename);
      continue;
    }
    if (
      !filename.endsWith(".tsx") ||
      filename.endsWith(".test.tsx") ||
      filename.endsWith(`${path.sep}i18n.tsx`)
    )
      continue;
    const code = fs.readFileSync(filename, "utf8");
    const source = ts.createSourceFile(
      filename,
      code,
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TSX,
    );
    const visit = (node) => {
      if (ts.isJsxText(node)) {
        const value = normalizeJsxText(node.getText(source));
        if (value.trim()) sources.add(value);
      } else if (
        ts.isJsxAttribute(node) &&
        translatableAttributes.has(node.name.getText(source)) &&
        node.initializer
      ) {
        if (ts.isStringLiteral(node.initializer))
          sources.add(node.initializer.text);
        else if (
          ts.isJsxExpression(node.initializer) &&
          node.initializer.expression
        )
          addStaticStringLiterals(node.initializer.expression);
      } else if (
        ts.isPropertyAssignment(node) &&
        ts.isIdentifier(node.name) &&
        translatableProperties.has(node.name.text)
      ) {
        addStaticStringLiterals(node.initializer);
      } else if (
        ts.isCallExpression(node) &&
        ts.isIdentifier(node.expression) &&
        node.expression.text === "tx" &&
        ts.isStringLiteral(node.arguments[0])
      ) {
        sources.add(node.arguments[0].text);
      } else if (
        ts.isCallExpression(node) &&
        ts.isIdentifier(node.expression) &&
        ["setError", "setNotice", "notify"].includes(node.expression.text) &&
        node.arguments[0]
      ) {
        addStaticStringLiterals(node.arguments[0]);
      } else if (
        ts.isJsxExpression(node) &&
        node.expression &&
        !ts.isJsxAttribute(node.parent)
      ) {
        addResultStrings(node.expression);
      }
      ts.forEachChild(node, visit);
    };
    visit(source);
  }
}
inspectDirectory(sourceRoot);

const missing = [...sources].filter((value) => !translations.has(value)).sort();
console.log(
  `Interface strings: ${sources.size}; English translations: ${translations.size}; missing: ${missing.length}`,
);
if (missing.length) {
  console.error(missing.map((value) => `- ${JSON.stringify(value)}`).join("\n"));
  process.exitCode = 1;
}
