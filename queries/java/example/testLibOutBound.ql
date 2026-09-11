/**
 * @kind problem
 * @id test-libsources
 * @problem.severity info
 */

import java
import semmle.code.java.dataflow.DataFlow
import libOutBound


from DataFlow::Node sink
where outBoundSink(sink)
select sink, "Location:" + sink.getLocation().toString()