/**
 * @name Python Class Definitions
 * @description Extract class definitions for dataclasses, Pydantic models, SQLAlchemy models
 * @kind problem
 * @problem.severity info
 * @id python/class-definitions
 * @tags class-extraction
 */

import python

from Class cls
where
  not cls.getLocation().getFile().getRelativePath().matches("%/site-packages/%")
  and not cls.getLocation().getFile().getRelativePath().matches("%/lib/python%")
  and not cls.getLocation().getFile().getRelativePath().matches("%/__pycache__/%")
  and not cls.getLocation().getFile().getRelativePath().matches("%/venv/%")
  and not cls.getLocation().getFile().getRelativePath().matches("%/virtualenv/%")
  and not cls.getLocation().getFile().getRelativePath().matches("%/pytest/%")
  and not cls.getLocation().getFile().getRelativePath().matches("%/unittest/%")
  and exists(cls.getLocation().getFile())
  and cls.getLocation().getFile().getRelativePath().matches("%.py")
  and cls.getName().length() > 0

select
  cls,
  cls.getName() + "@" +
  cls.getLocation().getFile().getRelativePath() + ":" +
  cls.getLocation().getStartLine().toString() +
  "|" + cls.getName() +
  "|" + cls.getLocation().getFile().getRelativePath() +
  "|" + cls.getLocation().getStartLine().toString() +
  "|" + cls.getLocation().getEndLine().toString() +
  "|" + cls.getLocation().getFile().getRelativePath()
          .regexpReplaceAll("/[^/]+\\.py$", "")
          .regexpReplaceAll("^(src|lib)/", "")
          .replaceAll("/", ".") +
  "|" + concat(Expr d |
          d = cls.getADecorator() |
          d.toString(),
          ","
        ) +
  // Fields: use assignment target names only; avoid getValue().toString() which can produce
  // expressions containing pipe characters that corrupt the 8-field row format.
  // Type annotation extraction requires the AnnAssign AST node; for safety we emit name only.
  "|" + concat(AssignStmt a |
          a.getScope() = cls |
          a.getATarget().toString() + ":",
          ","
        )
