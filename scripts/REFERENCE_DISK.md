# Авторская процедура с дисковым хранилищем

Режим replay_reference.py --disk-cache использует авторские функции FastWY на Python. Каждый бакет покрытий находится на диске. На GSE6462 это обходит MemoryError, но каждая перестановка многократно создаёт Python-объекты.

Скрипт replay_native.py использует тот же порт, порядок поддержек, строгое условие остановки, исходные FunctionOfX.calPValue, funcF, adjustedThreshold, adjustPval и перечисление значимых наборов. Подсчёт положительных меток и выбор минимума внутри уже перечисленного бакета выполняются в C++. Новая пара (поддержка, число положительных) передаётся через callback исходной функции Фишера. Её численный результат сохраняется без преобразований, включая нули и inf.

Хранилище содержит длины и 32-битные индексы признаков и строк. C++ читает его через отображение файлов Windows. Порядок записей сохраняется. После первого просмотра бакет неизменяем. Временные файлы и отображения освобождаются в конце запуска. Дисковый режим и native-подсчёт имеют отдельные протоколы.

## Сборка на Windows x64

Требуется Python x64 и компилятор x64. В x64 Native Tools Command Prompt for Visual Studio выполнить из корня проекта:

    cl /nologo /std:c++14 /EHsc /O2 /LD /MT scripts/reference_scan.cpp /Fobuild/reference_scan.obj /link /OUT:build/reference_scan.dll

В качестве альтернативы подходит x86_64-w64-mingw32-g++ с -std=c++14 -O2 -shared -static-libgcc -static-libstdc++. Разрядности Python и DLL должны совпадать. Основной прототип FastWY собирается отдельно. Вспомогательную DLL использует эталонный режим.

## Проверка

    python tests/test_reference_storage.py
    python scripts/replay_native.py --scanner build/reference_scan.dll build/reference/lamp-master inputs permutations.csv author.log --disk-cache D:/FastWY-cache --count 1000 --progress > author-native.tsv
    python scripts/compare_reference_replays.py author-original.tsv author-native.tsv

Последняя команда сравнивает все minP, поддержки остановки, число кандидатов, порог и находки, исключая пути файлов и таймеры. Значения Fisher вычисляются исходной Python-функцией автора.

## Интерпретация памяти

Счётчик peak_tree_commit_bytes измеряет выделенную память Windows Job Object. Отображённые файлы используют страницы файлового кэша ОС. Дополнительно в stderr native-режим выводит peak_root_working_set_bytes — пик физически резидентных страниц основного Python-процесса, и peak_root_commit_bytes. Эти счётчики имеют разный смысл и приводятся раздельно.

Документация Working Set:
https://learn.microsoft.com/en-us/windows/win32/api/psapi/ns-psapi-process_memory_counters
