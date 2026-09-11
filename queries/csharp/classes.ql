/**
 * @name C# Class Definitions
 * @description Extract class definitions (DTOs, entities, request/response models)
 * @kind problem
 * @problem.severity info
 * @id csharp/class-definitions
 * @tags class-extraction dto-extraction
 */

import csharp

from Class cls
where
  not cls.getName().matches("<%>%")
  and not cls.getNamespace().getFullName().matches("%.Tests.%")
  and not cls.getNamespace().getFullName().matches("%.Test.%")
  and not cls.getNamespace().getFullName().matches("NUnit.%")
  and not cls.getNamespace().getFullName().matches("xunit.%")
  and not cls.getNamespace().getFullName().matches("Microsoft.VisualStudio.TestTools.%")
  and exists(cls.getLocation().getFile())
  and cls.getLocation().getFile().getRelativePath().matches("%.cs")
  and not cls.getLocation().getFile().getRelativePath().matches("%.g.cs")
  and not cls.getLocation().getFile().getRelativePath().matches("%.Designer.cs")
  and cls.getName().length() > 0
  and exists(cls.getNamespace())
  and (
    exists(Attribute a |
      a = cls.getAnAttribute() and
      a.getType().getName() in [
        "ApiController", "Controller", "FromBody",
        "Table", "Entity", "DataContract"
      ]
    )
    or cls.getName().matches("%Dto")
    or cls.getName().matches("%DTO")
    or cls.getName().matches("%Request")
    or cls.getName().matches("%Response")
    or cls.getName().matches("%Model")
    or cls.getName().matches("%Entity")
    or cls.getName().matches("%ViewModel")
  )

select
  cls,
  cls.getName() + "@" +
  cls.getLocation().getFile().getRelativePath() + ":" +
  cls.getLocation().getStartLine().toString() +
  "|" + cls.getName() +
  "|" + cls.getLocation().getFile().getRelativePath() +
  "|" + cls.getLocation().getStartLine().toString() +
  "|" + cls.getLocation().getEndLine().toString() +
  "|" + cls.getNamespace().getFullName() +
  "|" + concat(Attribute a |
          a = cls.getAnAttribute() |
          a.getType().getName(),
          ","
        ) +
  "|" + concat(string member |
          (
            exists(Property p | p.getDeclaringType() = cls and
              member = p.getName() + ":" + p.getType().getName())
            or
            exists(Field f | f.getDeclaringType() = cls and f.isPublic() and
              member = f.getName() + ":" + f.getType().getName())
          ) |
          member, ","
        )
