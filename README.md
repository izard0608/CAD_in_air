# Profile类
## 包含两个可调用函数
- ``start()`` 启动Profile
- ``end(filename)`` 结束Profile，该函数调用后会自动在**ProfileResults**文件夹内生成三个文件，分别是``.prof``，``.txt``和``.svg``，分别是原始二进制文件，可读版本和火焰图（**注意：调用该函数时``filename``一定要包含后缀``.prof``！！！！**）
## 使用例见``START.py``