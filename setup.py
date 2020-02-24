import setuptools

setuptools.setup(
    name="kitipy",
    version="0.1",
    description="KNP task runner to automate and ease dev and ops workflows",
    license="MIT",
    packages=setuptools.find_packages(),
    install_requires=[
        "click>=7.0",
        "paramiko>=2.6.0",
        "PyYAML>=5.1",
        "requests>=2.23.0",
        "boto3>=1.12.5",
        "boto3-stubs[secretsmanager]>=*",
    ],
)
