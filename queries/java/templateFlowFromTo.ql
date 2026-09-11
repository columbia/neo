/**
 * @name Qflow: taint from a named source to a named sink
 * @description Parameterised intra-service flow query. {{FROM}} / {{TO}} are
 *              filled with CodeQL regexes by src/genquery/gen_flowfromto.py.
 * @kind path-problem
 * @problem.severity info
 * @id neo/qflow
 */

import java
import semmle.code.java.dataflow.TaintTracking
import semmle.code.java.dataflow.FlowSources

predicate fromSpec(DataFlow::Node n) {
  exists(MethodCall mc |
    mc.getMethod().getName().regexpMatch("{{FROM}}") and n.asExpr() = mc
  )
  or
  exists(ClassInstanceExpr cie |
    cie.getConstructedType().getName().regexpMatch("{{FROM}}") and n.asExpr() = cie
  )
  or
  exists(VarAccess va | va.getVariable().getName().regexpMatch("{{FROM}}") and n.asExpr() = va)
  or
  exists(Parameter p | p.getName().regexpMatch("{{FROM}}") and n.asParameter() = p)
  or
  "{{FROM}}".toLowerCase().regexpMatch(".*(request|user|input|source|param|remote|body|query|form).*") and
  n instanceof RemoteFlowSource
}

predicate toSpec(DataFlow::Node n) {
  exists(MethodCall mc |
    mc.getMethod().getName().regexpMatch("{{TO}}") and
    (mc.getAnArgument() = n.asExpr() or mc.getQualifier() = n.asExpr())
  )
  or
  exists(ClassInstanceExpr cie |
    cie.getConstructedType().getName().regexpMatch("{{TO}}") and cie.getAnArgument() = n.asExpr()
  )
}

module Cfg implements DataFlow::ConfigSig {
  predicate isSource(DataFlow::Node n) { fromSpec(n) }

  predicate isSink(DataFlow::Node n) { toSpec(n) }
}

module Flow = TaintTracking::Global<Cfg>;

import Flow::PathGraph

from Flow::PathNode source, Flow::PathNode sink
where Flow::flowPath(source, sink)
select sink.getNode(), source, sink, "QFLOW|{{FROM}}|{{TO}}"
