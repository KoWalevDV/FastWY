execute_process(
    COMMAND "${PROGRAM}" "${SOURCE}/data/sample_item.csv"
            "${SOURCE}/data/sample_expression_over1.csv" --exact
    RESULT_VARIABLE status OUTPUT_VARIABLE actual ERROR_VARIABLE error
)
if(NOT status EQUAL 0)
    message(FATAL_ERROR "fastwy failed: ${error}")
endif()
file(READ "${SOURCE}/tests/toy_expected.tsv" expected)
string(REPLACE "\r\n" "\n" actual "${actual}")
string(REPLACE "\r\n" "\n" expected "${expected}")
if(NOT actual STREQUAL expected)
    message(FATAL_ERROR "Expected:\n${expected}\nActual:\n${actual}")
endif()
