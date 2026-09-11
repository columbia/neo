/**
 * @name Simple Call Site Resolution (Go)
 * @description Clean mapping from call location to target function
 * @kind problem
 * @problem.severity info
 * @id go/simple-call-resolution
 */

import go

from DataFlow::CallNode call, Function callee
where
  call.getTarget() = callee and
  // Ensure valid locations exist
  exists(call.asExpr()) and
  exists(callee.getFuncDecl()) and
  // Exclude standard library (has qualified name starting with known stdlib packages)
  not callee.hasQualifiedName(["os", "fmt", "io", "net", "time", "context", "sync", "strings", "bytes", "encoding", "crypto", "database", "runtime", "reflect", "errors", "sort", "math", "log", "regexp", "bufio", "path", "flag", "testing", "strconv", "unicode", "container"], _) and
  // Exclude vendor directory
  not callee.getFuncDecl().getFile().getRelativePath().matches("%/vendor/%") and
  // Include test files (they contain application code we want to track)
  callee.getFuncDecl().getFile().getRelativePath().matches("%.go")
select call,
  call.asExpr().getFile().getRelativePath() + ":" +
  call.asExpr().getLocation().getStartLine().toString() + ":" +
  call.asExpr().getLocation().getStartColumn().toString() +
  " -> " +
  callee.getName() + "@" +
  callee.getFuncDecl().getFile().getRelativePath() + ":" +
  callee.getLocation().getStartLine().toString()