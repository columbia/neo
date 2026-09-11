#!/bin/bash

app="$1"
query="$2"


echo "Running on $app the query $query...."

# Check if query file exists (add quotes)
if [ ! -e "$query" ]; then
    echo "Query $query does not exist"
    echo "./run_codeql.sh app query"
    exit 1
fi

# Check if database directory exists
database="../../databases/$app"
# echo "Database path: $database"
if [ ! -d "$database" ]; then
    echo "Database $database does not exist"
    exit 1
fi

# Check if codebase directory exists (fix path and add quotes)
codebase="../../codebases/$app"
if [ ! -d "$codebase" ]; then
    echo "Codebase $codebase does not exist"
    exit 1
fi

query_name=$(basename "$query" .ql)
# Run CodeQL analysis (fix paths)
codeql database analyze "$database" \
    --search-path "../../codeql-lib" \
    --format sarif-latest \
    --output "$codebase/tmp.$query_name.sarif" \
    --rerun "$query" 
