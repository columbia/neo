/**
 * @name Java Class Definitions (DTOs, Entities, Forms)
 * @description Extract class definitions with field metadata for security analysis
 * @kind problem
 * @problem.severity info
 * @id java/class-definitions
 * @tags class-extraction dto-extraction
 */

import java

from RefType clazz
where
  // Only include actual classes (not interfaces, enums, or anonymous classes)
  clazz instanceof Class
  and not clazz instanceof Interface
  and not clazz.(Class).isAnonymous()
  and not clazz instanceof EnumType

  // Filter for relevant classes: DTOs, entities, forms, request/response objects
  and (
    // By annotation
    exists(Annotation a |
      a = clazz.getAnAnnotation() and
      a.getType().getName() in [
        "Data",           // Lombok @Data
        "Entity",         // JPA @Entity
        "Table",          // JPA @Table
        "Document",       // MongoDB @Document
        "RestController", // Spring @RestController
        "Controller",     // Spring @Controller
        "Component",      // Spring @Component
        "Service",        // Spring @Service
        "Repository"      // Spring @Repository
      ]
    )
    // By naming convention
    or clazz.getName().matches("%Dto")
    or clazz.getName().matches("%DTO")
    or clazz.getName().matches("%Form")
    or clazz.getName().matches("%Request")
    or clazz.getName().matches("%Response")
    or clazz.getName().matches("%Entity")
    or clazz.getName().matches("%Bean")
    or clazz.getName().matches("%Model")
    or clazz.getName().matches("%Vo")
    or clazz.getName().matches("%VO")
  )

  // Filter application code only (same pattern as functions.ql)
  and not clazz.getPackage().getName().matches("java.%")
  and not clazz.getPackage().getName().matches("javax.%")
  and not clazz.getPackage().getName().matches("org.junit.%")
  and not clazz.getPackage().getName().matches("org.mockito.%")
  and not clazz.getPackage().getName().matches("org.springframework.%")

  // Ensure valid locations
  and exists(clazz.getLocation().getFile())
  and clazz.getLocation().getFile().getRelativePath().matches("%.java")
  and not clazz.getLocation().getFile().getRelativePath().matches("%.class")

  // Must have valid name (not empty, not special characters)
  and clazz.getName().length() > 0
  and not clazz.getName().matches("%\n%")  // No newlines in name
  and not clazz.getName().matches("%;%")   // No semicolons

select
  clazz,
  // Pipe-delimited output for easy parsing:
  // class_id|name|file|start|end|package|annotations|fields
  clazz.getName() + "@" +
  clazz.getFile().getRelativePath() + ":" +
  min(int line |
    line = clazz.getAnAnnotation().getLocation().getStartLine() or
    line = clazz.getLocation().getStartLine()
  ).toString() +
  "|" + clazz.getName() +
  "|" + clazz.getFile().getRelativePath() +
  "|" + min(int line |
    line = clazz.getAnAnnotation().getLocation().getStartLine() or
    line = clazz.getLocation().getStartLine()
  ).toString() +
  "|" + clazz.getLocation().getEndLine().toString() +
  "|" + clazz.getPackage().getName() +
  "|" + concat(Annotation a |
    a = clazz.getAnAnnotation() |
    "@" + a.getType().getName(),
    ","
  ) +
  "|" + concat(Field f |
    f.getDeclaringType() = clazz |
    f.getName() + ":" + f.getType().getName(),
    ","
  )
