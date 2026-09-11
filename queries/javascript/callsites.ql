/**
 * @name Simple Call Site Resolution (JavaScript - AST-based)
 * @description Clean mapping from call location to target function using AST
 * @kind problem
 * @problem.severity info
 * @id javascript/simple-call-resolution-ast
 * @tags call-graph
 */

import javascript

from InvokeExpr call, FunctionDeclStmt callee
where
  // Match call to function by name
  call.getCalleeName() = callee.getIdentifier().getName() and
  // Both in same file (intra-procedural analysis)
  call.getFile() = callee.getFile() and
  // Filter application code only
  not call.getFile().getRelativePath().matches("node_modules/%") and
  // Only JavaScript files
  call.getFile().getRelativePath().matches("%.js")
select call,
       call.getFile().getRelativePath() + ":" +
       call.getLocation().getStartLine().toString() + ":" +
       call.getLocation().getStartColumn().toString() +
       " -> " +
       call.getCalleeName() + "@" +
       callee.getFile().getRelativePath() + ":" +
       callee.getLocation().getStartLine().toString()
