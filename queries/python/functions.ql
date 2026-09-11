/**
 * @name Python Function Definitions
 * @description Extract all function/method definitions with metadata including decorators
 * @kind problem
 * @problem.severity info
 * @id python/function-definitions
 * @tags function-extraction
 */

import python

string decoName(Expr d) {
  result = d.(Name).getId()
  or result = d.(Attribute).getName()
  or result = d.(Call).getFunc().(Attribute).getName()
  or result = d.(Call).getFunc().(Name).getId()
}

from Function func
where
  not func.getLocation().getFile().getRelativePath().matches("%/site-packages/%")
  and not func.getLocation().getFile().getRelativePath().matches("%/lib/python%")
  and not func.getLocation().getFile().getRelativePath().matches("%/__pycache__/%")
  and not func.getLocation().getFile().getRelativePath().matches("%/venv/%")
  and not func.getLocation().getFile().getRelativePath().matches("%/virtualenv/%")
  and not func.getLocation().getFile().getRelativePath().matches("%/pytest/%")
  and not func.getLocation().getFile().getRelativePath().matches("%/unittest/%")
  and exists(func.getLocation().getFile())
  and func.getLocation().getFile().getRelativePath().matches("%.py")
  and func.getName().length() > 0

select
  func,
  func.getName() + "@" +
  func.getLocation().getFile().getRelativePath() + ":" +
  func.getLocation().getStartLine().toString() +
  "|" + func.getName() +
  "|" + func.getLocation().getFile().getRelativePath() +
  "|" + func.getLocation().getStartLine().toString() +
  "|" + max(Stmt s | s.getScope() = func | s.getLocation().getEndLine()).toString() +
  "|" + "def " + func.getName() + "(" +
        concat(string p | p = func.getArgName(_) | p, ", ") +
        "):" +
  "|" + concat(string c | c = func.getEnclosingScope().(Class).getName() | c) +
  "|" + func.getLocation().getFile().getRelativePath()
          .regexpReplaceAll("/[^/]+\\.py$", "")
          .regexpReplaceAll("^(src|lib)/", "")
          .replaceAll("/", ".") +
  "|" + concat(Expr d | d = func.getADecorator() | decoName(d), ",")
