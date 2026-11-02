import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import ts from "typescript";

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

function normalizeJsxText(raw: string): string {
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

function staticInterfaceI18n() {
  return {
    name: "citalab-static-interface-i18n",
    enforce: "pre" as const,
    transform(code: string, id: string) {
      const file = id.split("?")[0].replaceAll("\\", "/");
      if (
        !file.includes("/src/") ||
        !file.endsWith(".tsx") ||
        file.endsWith(".test.tsx") ||
        file.endsWith("/i18n.tsx")
      )
        return null;
      const source = ts.createSourceFile(
        file,
        code,
        ts.ScriptTarget.Latest,
        true,
        ts.ScriptKind.TSX,
      );
      const edits: { start: number; end: number; text: string }[] = [];
      const quote = (value: string) => JSON.stringify(value);
      const translateResultStrings = (part: ts.Node) => {
        if (ts.isParenthesizedExpression(part)) {
          translateResultStrings(part.expression);
        } else if (ts.isConditionalExpression(part)) {
          translateResultStrings(part.whenTrue);
          translateResultStrings(part.whenFalse);
        } else if (
          ts.isBinaryExpression(part) &&
          [
            ts.SyntaxKind.AmpersandAmpersandToken,
            ts.SyntaxKind.BarBarToken,
            ts.SyntaxKind.QuestionQuestionToken,
          ].includes(part.operatorToken.kind)
        ) {
          translateResultStrings(part.right);
        } else if (ts.isStringLiteral(part)) {
          edits.push({
            start: part.getStart(source),
            end: part.getEnd(),
            text: `tx(${quote(part.text)})`,
          });
        }
      };
      const visit = (node: ts.Node) => {
        if (ts.isJsxText(node)) {
          const normalized = normalizeJsxText(node.getText(source));
          if (normalized.trim())
            edits.push({
              start: node.getStart(source),
              end: node.getEnd(),
              text: `{tx(${quote(normalized)})}`,
            });
        } else if (
          ts.isPropertyAssignment(node) &&
          ts.isIdentifier(node.name) &&
          translatableProperties.has(node.name.text)
        ) {
          translateResultStrings(node.initializer);
        } else if (
          ts.isJsxAttribute(node) &&
          translatableAttributes.has(node.name.getText(source)) &&
          node.initializer
        ) {
          if (ts.isStringLiteral(node.initializer)) {
            edits.push({
              start: node.initializer.getStart(source),
              end: node.initializer.getEnd(),
              text: `{tx(${quote(node.initializer.text)})}`,
            });
          } else if (
            ts.isJsxExpression(node.initializer) &&
            node.initializer.expression
          ) {
            translateResultStrings(node.initializer.expression);
          }
        } else if (
          ts.isJsxExpression(node) &&
          node.expression &&
          !ts.isJsxAttribute(node.parent)
        ) {
          translateResultStrings(node.expression);
        }
        ts.forEachChild(node, visit);
      };
      visit(source);
      if (!edits.length) return null;
      let output = code;
      for (const edit of edits.sort((left, right) => right.start - left.start))
        output = `${output.slice(0, edit.start)}${edit.text}${output.slice(edit.end)}`;
      const sourceRoot = path.resolve(process.cwd(), "src");
      const importPath = path
        .relative(path.dirname(file), path.join(sourceRoot, "i18n"))
        .replaceAll("\\", "/");
      const specifier = importPath.startsWith(".") ? importPath : `./${importPath}`;
      const localizedImport = /import\s*\{[^}]*\btx\b[^}]*\}\s*from\s+["'][^"']+["'];/.test(code);
      return {
        code: `${localizedImport ? "" : `import { tx } from ${quote(specifier)};\n`}${output}`,
        map: null,
      };
    },
  };
}

export default defineConfig({
  plugins: [staticInterfaceI18n(), react()],
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8765" },
  },
});
