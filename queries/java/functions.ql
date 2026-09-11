/**
 * @name Java Function Definitions
 * @description Extract all function/method definitions with metadata including annotations
 * @kind problem
 * @problem.severity info
 * @id java/function-definitions
 * @tags function-extraction
 */

import java

from Callable callable
where
  // Only include actual methods and constructors (not lambdas, anonymous classes, etc.)
  (callable instanceof Method or callable instanceof Constructor)

  // Filter application code only (same pattern as callsites.ql)
  and not callable.getDeclaringType().getPackage().getName().matches("java.%")
  and not callable.getDeclaringType().getPackage().getName().matches("javax.%")
  and not callable.getDeclaringType().getPackage().getName().matches("org.junit.%")
  and not callable.getDeclaringType().getPackage().getName().matches("org.mockito.%")
  and not callable.getDeclaringType().getPackage().getName().matches("org.springframework.%")

  // Ensure valid locations
  and exists(callable.getLocation().getFile())
  and callable.getLocation().getFile().getRelativePath().matches("%.java")
  and not callable.getLocation().getFile().getRelativePath().matches("%.class")

  // Must have a valid declaring type (class/interface)
  and exists(callable.getDeclaringType())

  // Must have a valid name (not empty, not special characters)
  and callable.getName().length() > 0
  and not callable.getName().matches("%\n%")  // No newlines in name
  and not callable.getName().matches("%;%")   // No semicolons
  and not callable.getName().matches("%,%")   // No commas
  and not callable.getName().matches("%\\*%") // No asterisks

select
  callable,
  // Pipe-delimited output for easy parsing:
  // function_id|name|file|start|end|signature|class|package|annotations
  callable.getName() + "@" +
  callable.getFile().getRelativePath() + ":" +
  min(int line |
    line = callable.getAnAnnotation().getLocation().getStartLine() or
    line = callable.getLocation().getStartLine()
  ).toString() +
  "|" + callable.getName() +
  "|" + callable.getFile().getRelativePath() +
  "|" + min(int line |
    line = callable.getAnAnnotation().getLocation().getStartLine() or
    line = callable.getLocation().getStartLine()
  ).toString() +
  "|" + max(int line |
    line = callable.getBody().getLocation().getEndLine() or
    line = callable.getLocation().getEndLine()
  ).toString() +
  "|" + callable.getStringSignature() +
  "|" + callable.getDeclaringType().getName() +
  "|" + callable.getDeclaringType().getPackage().getName() +
  "|" + concat(Annotation a |
    a = callable.getAnAnnotation() |
    "@" + a.getType().getName(),
    ","
  )
