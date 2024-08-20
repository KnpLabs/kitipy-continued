import setuptools

setuptools.setup(
    name="kitipy",
    version="0.4",
    description="KNP task runner to automate and ease dev and ops workflows",
    license="MIT",
    packages=setuptools.find_packages(),
    install_requires=[
        "boto3-stubs[ecr]==1.35.1",
        "boto3-stubs[ecs]==1.35.1",
        "boto3-stubs[secretsmanager]==1.35.1",
        "boto3==1.35.1",
        "click==7.1.2",
        "Jinja2==3.1.4",
        "paramiko==3.4.1",
        "PyYAML==6.0.2",
        "requests==2.32.3",
        "markupsafe==2.1.5"
    ]
)
