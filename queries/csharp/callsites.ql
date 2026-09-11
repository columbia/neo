/**
 * @name Simple Call Site Resolution (C#)
 * @description Clean mapping from call location to target method (function_name@file:line format)
 * @kind problem
 * @problem.severity info
 * @id csharp/simple-call-resolution
 * @tags call-graph
 */

import csharp

from Call call, Callable callee
where call.getARuntimeTarget() = callee
  // Exclude calls from test namespaces (caller side)
  and not call.getEnclosingCallable().getDeclaringType().getNamespace().getFullName().matches("%.Tests.%")
  and not call.getEnclosingCallable().getDeclaringType().getNamespace().getFullName().matches("%.Test.%")
  and not call.getEnclosingCallable().getDeclaringType().getNamespace().getFullName().matches("NUnit.%")
  and not call.getEnclosingCallable().getDeclaringType().getNamespace().getFullName().matches("xunit.%")
  and not call.getEnclosingCallable().getDeclaringType().getNamespace().getFullName().matches("Microsoft.VisualStudio.TestTools.%")
  // Exclude calls to test namespaces (callee side)
  and not callee.getDeclaringType().getNamespace().getFullName().matches("%.Tests.%")
  and not callee.getDeclaringType().getNamespace().getFullName().matches("%.Test.%")
  and not callee.getDeclaringType().getNamespace().getFullName().matches("NUnit.%")
  and not callee.getDeclaringType().getNamespace().getFullName().matches("xunit.%")
  and not callee.getDeclaringType().getNamespace().getFullName().matches("Microsoft.VisualStudio.TestTools.%")
  and not callee instanceof Accessor
  and exists(call.getLocation().getFile())
  and exists(callee.getLocation().getFile())
  and callee.getLocation().getFile().getRelativePath().matches("%.cs")
  and not callee.getLocation().getFile().getRelativePath().matches("%.g.cs")
  and not callee.getLocation().getFile().getRelativePath().matches("%.Designer.cs")

select call,
  call.getLocation().getFile().getRelativePath() + ":" +
  call.getLocation().getStartLine().toString() + ":" +
  call.getLocation().getStartColumn().toString() +
  " -> " +
  callee.getName() + "@" +
  callee.getLocation().getFile().getRelativePath() + ":" +
  callee.getLocation().getStartLine().toString()
