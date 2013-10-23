from distutils.core import setup
setup(
    name='pyCAN',
    version='0.1',
    author='Adam Lewis',
    author_email='adam.lewis@questrail.com',
    packages=['pycan','pycan.tools', 'pycan.tools.parsers', 'pycan.drivers'],
    url='http://github.com/questrail/pycan',
    license='LICENSE.txt',
    description='Generic Python Controller Area Network (CAN) driver abstraction.',
    requires=['pyserial (>=2.6)',],
    classifiers=[
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Development Status :: 3 - Alpha',
        'Operating System :: OS Independent',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ]
)
