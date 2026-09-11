/**
 * @name Simple Call Site Resolution (Python)
 * @description Clean mapping from call location to target function (simplified IDs)
 * @kind problem
 * @problem.severity info
 * @id neo
 */

import python

from CallNode call, Value val, Function callee
where call = val.getACall() and
      val.(CallableValue).getScope() = callee
  // Filter application code only - exclude standard library and common third-party packages
  and not callee.getLocation().getFile().getRelativePath().matches("%/site-packages/%")
  and not callee.getLocation().getFile().getRelativePath().matches("%/lib/python%")
  and not callee.getLocation().getFile().getRelativePath().matches("%/__pycache__/%")
  and not callee.getLocation().getFile().getRelativePath().matches("%/venv/%")
  and not callee.getLocation().getFile().getRelativePath().matches("%/virtualenv/%")
  and not callee.getLocation().getFile().getRelativePath().matches("%/pytest/%")
  and not callee.getLocation().getFile().getRelativePath().matches("%/unittest/%")
  // Ensure valid locations
  and exists(call.getLocation().getFile())
  and exists(callee.getLocation().getFile())
  and callee.getLocation().getFile().getRelativePath().matches("%.py")
select call,
       call.getLocation().getFile().getRelativePath() + ":" + 
       call.getLocation().getStartLine().toString() + ":" +
       call.getLocation().getStartColumn().toString() +
       " -> " +
       callee.getName() + "@" +
       callee.getLocation().getFile().getRelativePath() + ":" +
       callee.getLocation().getStartLine().toString()