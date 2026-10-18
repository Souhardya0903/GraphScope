// Parse source only: do not load repository modules, tsconfig plugins, or scripts.
const ts = require('typescript');
let input = '';
process.stdin.setEncoding('utf8');
process.stdin.on('data', chunk => input += chunk);
process.stdin.on('end', () => {
  const files = JSON.parse(input), output = [];
  for (const [path, text] of Object.entries(files)) {
    const source = ts.createSourceFile(path, text, ts.ScriptTarget.Latest, true);
    const row = {path, functions: [], calls: [], imports: {}, gaps: [], resources: [], exports: {}};
    const line = node => source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1;
    const end = node => source.getLineAndCharacterOfPosition(node.end).line + 1;
    const literal = node => node && ts.isStringLiteralLike(node) ? node.text : null;
    const functions = new Map(), bindings = new Map();
    const names = node => ts.isIdentifier(node) ? [node.text] : (ts.isObjectBindingPattern(node) || ts.isArrayBindingPattern(node)) ? node.elements.flatMap(el => ts.isBindingElement(el) ? names(el.name) : []) : [];
    const bind = name => bindings.set(name, (bindings.get(name) || 0) + 1);
    function define(name, node, declaration) {
      bind(name);
      const fn = {name, line: line(declaration), end: end(declaration), async: !!node.modifiers?.some(m => m.kind === ts.SyntaxKind.AsyncKeyword),
        parameters: node.parameters.map(p => p.name.getText(source)), calls: [], node};
      row.functions.push(fn); functions.set(name, fn);
      if (declaration.modifiers?.some(m => m.kind === ts.SyntaxKind.ExportKeyword)) {
        row.exports[declaration.modifiers.some(m => m.kind === ts.SyntaxKind.DefaultKeyword) ? 'default' : name] = name;
      }
    }
    for (const stmt of source.statements) {
      if (ts.isImportDeclaration(stmt) && stmt.importClause) {
        const mod = literal(stmt.moduleSpecifier), clause = stmt.importClause;
        if (clause.isTypeOnly) continue;
        if (clause.name) { bind(clause.name.text); row.imports[clause.name.text] = [mod, 'default']; }
        if (clause.namedBindings && ts.isNamedImports(clause.namedBindings)) {
          for (const el of clause.namedBindings.elements) { if (el.isTypeOnly) continue; bind(el.name.text); row.imports[el.name.text] = [mod, el.propertyName?.text || el.name.text]; }
        } else if (clause.namedBindings) {
          bind(clause.namedBindings.name.text); row.imports[clause.namedBindings.name.text] = [mod, null];
        }
      } else if (ts.isFunctionDeclaration(stmt) && stmt.name && stmt.body) define(stmt.name.text, stmt, stmt);
      else if (ts.isVariableStatement(stmt)) {
        for (const d of stmt.declarationList.declarations) {
          if (ts.isIdentifier(d.name) && d.initializer && (ts.isArrowFunction(d.initializer) || ts.isFunctionExpression(d.initializer))) define(d.name.text, d.initializer, stmt);
          else if (ts.isIdentifier(d.name)) bind(d.name.text);
        }
      } else if (ts.isClassDeclaration(stmt)) row.gaps.push({line: line(stmt), reason: 'JavaScript/TypeScript class and inheritance dispatch unsupported'});
      else if (ts.isExportDeclaration(stmt)) row.gaps.push({line: line(stmt), reason: 'Re-exports require manual review'});
    }
    for (const fn of row.functions) {
      const blocked = new Set(fn.node.parameters.flatMap(p => names(p.name)));
      function locals(node) {
        if (node !== fn.node && (ts.isFunctionLike(node) || ts.isClassDeclaration(node))) {
          if (node.name) blocked.add(node.name.getText(source));
          return;
        }
        if (ts.isVariableDeclaration(node) || ts.isParameter(node)) names(node.name).forEach(name => blocked.add(name));
        if (ts.isBinaryExpression(node) && node.operatorToken.kind >= ts.SyntaxKind.FirstAssignment && node.operatorToken.kind <= ts.SyntaxKind.LastAssignment) {
          blocked.add(node.left.getText(source).split('.')[0]);
        }
        ts.forEachChild(node, locals);
      }
      locals(fn.node.body);
      function visit(node) {
        if (node !== fn.node && (ts.isFunctionLike(node) || ts.isClassDeclaration(node))) {
          row.gaps.push({line: line(node), reason: 'Nested JavaScript function/class skipped'}); return;
        }
        if (ts.isCallExpression(node)) {
          const target = node.expression.getText(source), first = target.split('.')[0];
          fn.calls.push({target, line: line(node), end: end(node), column: node.getStart(source), blocked: blocked.has(first) || bindings.get(first) > 1});
          if (target === 'fetch' && !blocked.has('fetch') && !bindings.has('fetch')) {
            let method = 'GET';
            const options = node.arguments[1];
            if (options && ts.isObjectLiteralExpression(options)) {
              const prop = options.properties.find(p => p.name?.getText(source) === 'method');
              if (prop) method = literal(prop.initializer)?.toUpperCase() || null;
            }
            row.resources.push({owner: fn.name, line: line(node), column: node.getStart(source), value: literal(node.arguments[0]), method});
          }
        }
        ts.forEachChild(node, visit);
      }
      visit(fn.node.body);
      delete fn.node;
    }
    row.errors = source.parseDiagnostics.map(d => ({line: source.getLineAndCharacterOfPosition(d.start || 0).line + 1, reason: ts.flattenDiagnosticMessageText(d.messageText, '\n')}));
    output.push(row);
  }
  process.stdout.write(JSON.stringify(output));
});
