from setuptools import setup, find_packages

setup(
    name='starshareParser',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        # List your package dependencies here
        'numpy',
        'requests',
    ],
    entry_points={
        'console_scripts': [
            # Define any console scripts here
            # 'script_name = my_package.module:function'
        ],
    },
    author='Stefan Gabura',
    author_email='stefan.gabura@gmail.com',
    description='Using an extended version of sc2parser to parse events for Mindshare',
    long_description=open('README.rst').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/yourusername/my_project',  # Replace with your project's URL
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',  # Specify the Python versions you support
)
