import setuptools

setuptools.setup(
    name="kitipy",
    version="0.1",
    description="KNP task runner to automate and ease dev and ops workflows",
    license="MIT",
    packages=setuptools.find_packages(),
    install_requires=[
        "boto3-stubs[ecr]==1.26.62",
        "boto3-stubs[ecs]==1.26.62",
        "boto3-stubs[secretsmanager]==1.26.62",
        "boto3==1.23.7",
        "click==7.0.0",
        "Jinja2==2.7.0",
        "paramiko==2.6.0",
        "PyYAML==5.1.0",
        "requests==2.27.1",
        "markupsafe==2.0.1"
    ]
)
