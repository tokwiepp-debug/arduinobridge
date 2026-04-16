"""
Setup script for ArduinoBridge
"""

from setuptools import setup, find_packages

setup(
    name="arduino-bridge",
    version="0.1.0",
    description="Cross-platform Arduino programming tool with OpenClaw integration",
    author="Tobi",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "pyserial>=3.5",
        "pyusb>=1.2.1",
        "requests>=2.31.0",
        "flask>=3.0.0",
        "flask-cors>=4.0.0",
    ],
    entry_points={
        "console_scripts": [
            "arduino-bridge=arduino_bridge.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
)
