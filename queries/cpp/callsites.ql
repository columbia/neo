/**
 * @name Simple Call Site Resolution
 * @description Clean mapping from call location to target function (simplified IDs)
 * @kind problem
 * @problem.severity info
 * @id cpp/simple-call-resolution
 * @tags call-graph
 */

import cpp

from Call call, Function callee
where call.getTarget() = callee
  // Filter application code only - exclude standard library
  and not callee.getFile().getAbsolutePath().matches("%/usr/include/%")
  and not callee.getFile().getAbsolutePath().matches("%/include/c++/%")
  and not callee.getFile().getAbsolutePath().matches("%/mingw%/include/%")
  and not callee.getFile().getAbsolutePath().matches("%/MSVC/%/include/%")
  and not callee.getFile().getAbsolutePath().matches("%/Windows Kits/%/Include/%")
  // Exclude common test frameworks
  and not callee.getFile().getRelativePath().matches("%gtest%")
  and not callee.getFile().getRelativePath().matches("%catch%")
  and not callee.getFile().getRelativePath().matches("%boost/test%")
  // Skip test files
  and not call.getLocation().getFile().getRelativePath().matches("%/test/%")
  and not call.getLocation().getFile().getRelativePath().matches("%/tests/%")
  and not call.getLocation().getFile().getRelativePath().matches("%_test.%")
  and not call.getLocation().getFile().getRelativePath().matches("%Test.%")
  // Ensure valid locations and source files
  and exists(call.getLocation().getFile())
  and exists(callee.getLocation().getFile())
  and (callee.getLocation().getFile().getExtension() = "cpp" or
       callee.getLocation().getFile().getExtension() = "cc" or
       callee.getLocation().getFile().getExtension() = "cxx" or
       callee.getLocation().getFile().getExtension() = "c" or
       callee.getLocation().getFile().getExtension() = "h" or
       callee.getLocation().getFile().getExtension() = "hpp" or
       callee.getLocation().getFile().getExtension() = "hxx")
  // Exclude system headers and generated files
  and not callee.getLocation().getFile().getRelativePath().matches("%.o")
  and not callee.getLocation().getFile().getRelativePath().matches("%.so")
  and not callee.getLocation().getFile().getRelativePath().matches("%.dll")
select call,
       call.getLocation().getFile().getRelativePath() + ":" + 
       call.getLocation().getStartLine().toString() + ":" +
       call.getLocation().getStartColumn().toString() +
       " -> " +
       callee.getName() + "@" +  // Just function name
       callee.getFile().getRelativePath() + ":" +
       // Use function definition line (C/C++ doesn't have annotations like Java)
       callee.getLocation().getStartLine().toString()
