/**
 * @kind problem
 * @id test-libsources
 * @problem.severity info
 */

import java
import semmle.code.java.dataflow.DataFlow
import libSource


from DataFlow::Node source
where enhancedSource(source)
select source, "Location:" + source.getLocation().toString()

// ./run_codeql.sh test_libsink.ql java