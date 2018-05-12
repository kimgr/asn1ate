@ECHO OFF

REM For every *.asn file, run it through test.py and pipe
REM the result back to Python.
REM This checks two things:
REM 1) All steps of parsing and codegen run without exceptions
REM 2) The end result is valid Python
REM Note that it does not say anything about correctness or
REM completeness of the generated code.

FOR %%t IN (testdata\*.asn) DO (
  @ECHO Checking %%t
  RD /s /q _testdir
  MD _testdir
  python asn1ate\test.py --outdir=_testdir --gen %%t
  IF %ERRORLEVEL% NEQ 0 (
     EXIT /B %ERRORLEVEL%
  )

  FOR %%m IN (_testdir\*.py) DO (
    python %%m
    IF %ERRORLEVEL% NEQ 0 (
       EXIT /B %ERRORLEVEL%
    )
  )
)
