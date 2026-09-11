/**
 * @name C# Function Definitions
 * @description Extract all method, constructor and lambda/anonymous-method
 *              definitions with metadata including attributes
 * @kind problem
 * @problem.severity info
 * @id csharp/function-definitions
 * @tags function-extraction
 */

import csharp

/** Real name, or "anonymous" for a lambda/anonymous method -- minimal-API
 *  route handlers (app.MapGet(...)) and most callbacks are written inline,
 *  and they'd otherwise be excluded entirely (they're not a Method or
 *  Constructor, and have no name of their own). */
string cName(Callable c) {
  c.getName().length() > 0 and not c.getName().matches("%<anonymous%") and result = c.getName()
  or
  (c.getName().length() = 0 or c.getName().matches("%<anonymous%")) and result = "anonymous"
}

/** The declaring type to report: the callable's own for a Method/Constructor,
 *  or its enclosing callable's for a lambda (which has none of its own). */
ValueOrRefType cDeclaringType(Callable c) {
  not c instanceof AnonymousFunctionExpr and result = c.getDeclaringType()
  or
  exists(Callable enclosing | enclosing = c.(AnonymousFunctionExpr).getEnclosingCallable() |
    result = enclosing.getDeclaringType()
  )
}

bindingset[t]
string typeNameOrEmpty(ValueOrRefType t) { if exists(t) then result = t.getName() else result = "" }

bindingset[t]
string namespaceOrEmpty(ValueOrRefType t) {
  if exists(t) and exists(t.getNamespace()) then result = t.getNamespace().getFullName() else result = ""
}

from Callable callable, ValueOrRefType declType
where
  (callable instanceof Method or callable instanceof Constructor or callable instanceof AnonymousFunctionExpr)
  and declType = cDeclaringType(callable)
  and not namespaceOrEmpty(declType).matches("%.Tests.%")
  and not namespaceOrEmpty(declType).matches("%.Test.%")
  and not namespaceOrEmpty(declType).matches("NUnit.%")
  and not namespaceOrEmpty(declType).matches("xunit.%")
  and not namespaceOrEmpty(declType).matches("Microsoft.VisualStudio.TestTools.%")
  and exists(callable.getLocation().getFile())
  and callable.getLocation().getFile().getRelativePath().matches("%.cs")
  and not callable.getLocation().getFile().getRelativePath().matches("%.g.cs")
  and not callable.getLocation().getFile().getRelativePath().matches("%.Designer.cs")
  and cName(callable).length() > 0

select
  callable,
  cName(callable) + "@" +
  callable.getLocation().getFile().getRelativePath() + ":" +
  callable.getLocation().getStartLine().toString() +
  "|" + cName(callable) +
  "|" + callable.getLocation().getFile().getRelativePath() +
  "|" + callable.getLocation().getStartLine().toString() +
  "|" + callable.getLocation().getEndLine().toString() +
  "|" + callable.toStringWithTypes() +
  "|" + typeNameOrEmpty(declType) +
  "|" + namespaceOrEmpty(declType) +
  "|" + concat(Attribute a |
          a = callable.(Attributable).getAnAttribute() |
          a.getType().getName(),
          ","
        )
