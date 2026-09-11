/**
 * @name find flows from source to sink
 * @description Detects privileged operations with consistent argument handling
 * @kind path-problem
 * @problem.severity error
 * @precision high
 * @id java/consistent-privileged-operations
 * @tags security data-flow
 */
import java
import semmle.code.java.dataflow.DataFlow
import semmle.code.java.dataflow.TaintTracking
import semmle.code.java.dataflow.FlowSources
import semmle.code.java.dataflow.ApiSources as ApiSources
import semmle.code.java.dataflow.ApiSinks as ApiSinks
import semmle.code.java.security.QueryInjection
import libSources
import libSinks
import libOutBounds
import libInterServiceModels

module MyConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) {
    enhancedRemoteSource(source)
  }
  
  predicate isSink(DataFlow::Node sink) {
    privilegedSink(sink)
  }
  
  predicate isBarrier(DataFlow::Node node) {
    none()
  }
  
    predicate isAdditionalFlowStep(DataFlow::Node node1, DataFlow::Node node2) {
    outboundTaintStep(node1, node2)
    }
}

module MyFlow = TaintTracking::Global<MyConfig>;

// CRITICAL: This import is required for path-problem queries
import MyFlow::PathGraph

// For path-problem queries, you need these specific result patterns:
from MyFlow::PathNode source, MyFlow::PathNode sink
where MyFlow::flowPath(source, sink)
select sink.getNode(), source, sink,
   "Data from $@ flows to privileged sink.", 
  source.getNode(), "user input"