from common.helper import get_template_flow2sink_query, get_customize_checked_op_query, get_flow2sink_query, get_customize_op_query, san_appname, AnalysisStatus, check_status

def gen_flow2sink_query(language: str, appname: str):
    query_template = get_template_flow2sink_query(language)
    query_content = query_template.read_text()

    status_appname = appname
    sanitized_appname = san_appname(appname)

    if check_status(status_appname, AnalysisStatus.WRITE_CUSTOMEOP):
        query_content = query_content.replace("{{IMPORT_PLACEHOLDER1}}", f"import tmp.{sanitized_appname}SinkOp ")
        query_content = query_content.replace("{{SINK_PLACEHOLDER1}}", f"or customizeOp(sink) ")
    else:
        query_content = query_content.replace("{{IMPORT_PLACEHOLDER1}}", "")
        query_content = query_content.replace("{{SINK_PLACEHOLDER1}}", "//missing")
        
    if check_status(status_appname, AnalysisStatus.WRITE_CHECKEDOP):
        query_content = query_content.replace("{{IMPORT_PLACEHOLDER2}}", f"import tmp.{sanitized_appname}SinkCheckedOp ")
        query_content = query_content.replace("{{SINK_PLACEHOLDER2}}", f"or checkedOp(sink) ")
    else:
        query_content = query_content.replace("{{IMPORT_PLACEHOLDER2}}", "")
        query_content = query_content.replace("{{SINK_PLACEHOLDER2}}", "// missing")


    full_query_path = get_flow2sink_query(language, sanitized_appname)
    full_query_path.write_text(query_content)
    return full_query_path
