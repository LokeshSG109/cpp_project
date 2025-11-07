from setuptools import setup, find_packages

setup(
    name="smartnotifier",
    version="0.1.0",
    author="Your Name",
    author_email="your_email@example.com",
    description="A smart notification management library for cloud-based appointment systems.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/smartnotifier",
    packages=find_packages(),
    install_requires=[
        "boto3>=1.28.0"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)
