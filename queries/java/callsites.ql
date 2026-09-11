/**
 * @name Simple Call Site Resolution
 * @description Clean mapping from call location to target function (simplified IDs)
 * @kind problem
 * @problem.severity info
 * @id java/simple-call-resolution
 * @tags call-graph
 */

import java

from Call call, Callable callee
where call.getCallee() = callee
  // Filter application code only
  and not callee.getDeclaringType().getPackage().getName().matches("java.%")
  and not callee.getDeclaringType().getPackage().getName().matches("javax.%")
  and not callee.getDeclaringType().getPackage().getName().matches("org.junit.%")
  and not callee.getDeclaringType().getPackage().getName().matches("org.mockito.%")
  // Ensure valid locations
  and exists(call.getLocation().getFile())
  and exists(callee.getLocation().getFile())
  and callee.getLocation().getFile().getRelativePath().matches("%.java")
  and not  callee.getLocation().getFile().getRelativePath().matches("%.class")
select call,
       call.getLocation().getFile().getRelativePath() + ":" + 
       call.getLocation().getStartLine().toString() + ":" +
       call.getLocation().getStartColumn().toString() +
       " -> " +
       callee.getName() + "@" +  // Just function name, not qualified name
       callee.getFile().getRelativePath() + ":" +
    //    callee.getLocation().getStartLine().toString()
    // Use the earliest annotation's start line, or the method's start line if no annotations
       min(int line | 
           line = callee.getAnAnnotation().getLocation().getStartLine() or 
           line = callee.getLocation().getStartLine()
       ).toString()