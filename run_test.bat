@echo off
set PYTHONIOENCODING=utf-8
py -3 "%~dp0.codebuddy\skills\project-wiki\scripts\test_query_accuracy.py" > test_output.txt 2>&1
echo Exit code: %ERRORLEVEL%
type test_output.txt
