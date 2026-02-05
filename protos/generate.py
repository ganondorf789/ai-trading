#!/usr/bin/env python
"""
生成 gRPC Python 代码

运行方式：
cd protos
python generate.py

依赖安装：
pip install grpcio-tools
"""
import subprocess
import sys
import os

def main():
    proto_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(proto_dir)
    
    # 输出目录
    output_dir = project_root
    
    # Proto 文件
    proto_file = os.path.join(proto_dir, "trading_service.proto")
    
    print(f"Proto 目录: {proto_dir}")
    print(f"输出目录: {output_dir}")
    print(f"Proto 文件: {proto_file}")
    
    # 生成 Python 代码
    cmd = [
        sys.executable, "-m", "grpc_tools.protoc",
        f"-I{proto_dir}",
        f"--python_out={output_dir}",
        f"--pyi_out={output_dir}",
        f"--grpc_python_out={output_dir}",
        proto_file
    ]
    
    print(f"\n执行命令: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"错误: {result.stderr}")
        sys.exit(1)
    
    print("\n生成成功！")
    print(f"  - trading_service_pb2.py")
    print(f"  - trading_service_pb2.pyi")
    print(f"  - trading_service_pb2_grpc.py")

if __name__ == "__main__":
    main()
