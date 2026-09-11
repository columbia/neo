/**
 * @kind path-problem
 * @problem.severity error
 * @precision high
 * @id flow-source-sink
 */
import java
import semmle.code.java.dataflow.DataFlow
import semmle.code.java.dataflow.TaintTracking
import semmle.code.java.dataflow.FlowSources
import semmle.code.java.dataflow.ApiSources as ApiSources
import semmle.code.java.dataflow.ApiSinks as ApiSinks
import semmle.code.java.security.QueryInjection
import libSource
import libSink
{{IMPORT_PLACEHOLDER1}}
{{IMPORT_PLACEHOLDER2}}

module MyConfig implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node source) {
    enhancedSource(source)
  }
  
  predicate isSink(DataFlow::Node sink) {
    enhancedSink(sink)
    // or customizeOp(sink) 
    {{SINK_PLACEHOLDER1}}
    // or checkedOp(sink) 
    {{SINK_PLACEHOLDER2}}
  }
  
  predicate isBarrier(DataFlow::Node node) {
    // Block taint from entering MyBatis *Example query builder classes.
    // These classes (and their inner classes Criteria/GeneratedCriteria/Criterion) build
    // parameterized SQL via criteria objects — user data reaching them is safe in practice
    // (MyBatis uses prepared statements), and treating them as sinks produces enormous noise.
    // NOTE: check the METHOD's defining file (not the call site file), because inner classes
    // like Criteria/GeneratedCriteria do NOT have "Example" in their class name.
    exists(MethodCall mc |
      mc.getAnArgument() = node.asExpr() and
      mc.getMethod().getFile().getBaseName().matches("%Example.java")
    )
    or
    exists(ConstructorCall cc |
      cc.getAnArgument() = node.asExpr() and
      cc.getConstructor().getFile().getBaseName().matches("%Example.java")
    )
    or
    // Block taint from entering simple void setters on domain/entity/model/pojo objects,
    // whether the taint arrives via the ARGUMENT or the QUALIFIER (receiver object).
    // These are data-marshaling methods — the security-relevant sink is where the
    // populated object is later passed to a privileged operation (service/repository),
    // which is reported as a separate direct flow from the source.
    exists(MethodCall mc |
      (mc.getAnArgument() = node.asExpr() or mc.getQualifier() = node.asExpr()) and
      (
        // void setters (set*) — data marshaling only
        (mc.getMethod().getName().matches("set%") and mc.getMethod().getReturnType().hasName("void"))
        or
        // getters (get*, is*) — reading from a domain object is never a privileged sink
        mc.getMethod().getName().matches("get%") or
        mc.getMethod().getName().matches("is%")
      ) and
      (
        mc.getMethod().getDeclaringType().getPackage().getName().matches("%.domain") or
        mc.getMethod().getDeclaringType().getPackage().getName().matches("%.domain.%") or
        mc.getMethod().getDeclaringType().getPackage().getName().matches("%.entity") or
        mc.getMethod().getDeclaringType().getPackage().getName().matches("%.entity.%") or
        mc.getMethod().getDeclaringType().getPackage().getName().matches("%.model") or
        mc.getMethod().getDeclaringType().getPackage().getName().matches("%.model.%") or
        mc.getMethod().getDeclaringType().getPackage().getName().matches("%.pojo") or
        mc.getMethod().getDeclaringType().getPackage().getName().matches("%.pojo.%")
      )
    )
  }
  
  //   predicate isAdditionalFlowStep(DataFlow::Node node1, DataFlow::Node node2) {
  //   outBoundTaintStep(node1, node2)
  //   }
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
