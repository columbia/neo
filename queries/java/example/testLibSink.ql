/**
 * @kind problem
 * @id test-libsources
 * @problem.severity info
 */

import java
import semmle.code.java.dataflow.DataFlow
import libSink


from DataFlow::Node sink
where enhancedSink(sink)
select sink, "Location:" + sink.getLocation().toString()


// // CORRECTED MAIN QUERY - now properly identifies specific privileged calls
// from MethodCall call, DataFlow::Node sink
// where 
//   // Find the specific sink node within this call
//   privilegedSink(sink) and
//   (
//     // Sink is an argument to this call
//     sink.asExpr() = call.getAnArgument() or
//     // Sink is the qualifier of this call  
//     sink.asExpr() = call.getQualifier()
//   )
// select call, 
//   call.getMethod().getName() + 
//   " MORE INFO: " + call.getMethod().getDeclaringType().getQualifiedName() +
//   " SINK: " + sink.toString()

// ./run_codeql.sh test_libsource.ql java