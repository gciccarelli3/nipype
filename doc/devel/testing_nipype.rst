.. _dev_testing_nipype:

==============
Testing nipype
==============

In order to ensure the stability of each release of Nipype, the project uses two
continuous integration services: `CircleCI <https://circleci.com/gh/nipy/nipype/tree/master>`_
and `Travis CI <https://travis-ci.org/nipy/nipype>`_.
If both batteries of tests are passing, the following badges should be shown in green color:

.. image:: https://travis-ci.org/nipy/nipype.png?branch=master
  :target: https://travis-ci.org/nipy/nipype

.. image:: https://circleci.com/gh/nipy/nipype/tree/master.svg?style=svg
  :target: https://circleci.com/gh/nipy/nipype/tree/master


Installation for developers
---------------------------

To check out the latest development version::

    git clone https://github.com/nipy/nipype.git

After cloning::

    cd nipype
    pip install -r requirements.txt
    python setup.py develop

or::

    cd nipype
    pip install -r requirements.txt
    pip install -e .[tests]



Test implementation
-------------------

Nipype testing framework is built upon `nose <http://nose.readthedocs.io/en/latest/>`_.
By the time these guidelines are written, Nipype implements 17638 tests.

After installation in developer mode, the tests can be run with the
following simple command at the root folder of the project ::

    make tests

If ``make`` is not installed in the system, it is possible to run the tests using::

    python -W once:FSL:UserWarning:nipype `which nosetests` --with-doctest \
           --with-doctest-ignore-unicode --logging-level=DEBUG --verbosity=3 nipype


A successful test run should complete in a few minutes and end with
something like::

    ----------------------------------------------------------------------
    Ran 17922 tests in 107.254s

    OK (SKIP=27)


All tests should pass (unless you're missing a dependency). If the ``SUBJECTS_DIR```
environment variable is not set, some FreeSurfer related tests will fail.
If any of the tests failed, please report them on our `bug tracker
<http://github.com/nipy/nipype/issues>`_.

On Debian systems, set the following environment variable before running
tests::

       export MATLABCMD=$pathtomatlabdir/bin/$platform/MATLAB

where ``$pathtomatlabdir`` is the path to your matlab installation and
``$platform`` is the directory referring to x86 or x64 installations
(typically ``glnxa64`` on 64-bit installations).

Skip tests
~~~~~~~~~~

Nipype will skip some tests depending on the currently available software and data
dependencies. Installing software dependencies and downloading the necessary data
will reduce the number of skip tests.

Some tests in Nipype make use of some images distributed within the `FSL course data
<http://fsl.fmrib.ox.ac.uk/fslcourse/>`_. This reduced version of the package can be downloaded `here
<https://files.osf.io/v1/resources/nefdp/providers/osfstorage/57f472cf9ad5a101f977ecfe>`_.
To enable the tests depending on these data, just unpack the targz file and set the :code:`FSL_COURSE_DATA` environment
variable to point to that folder.


Avoiding any MATLAB calls from testing
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

On unix systems, set an empty environment variable::

    export NIPYPE_NO_MATLAB=

This will skip any tests that require matlab.


Testing Nipype using Docker
---------------------------

As of :code:`nipype-0.13`, Nipype is tested inside Docker containers. Once the developer
`has installed the Docker Engine <https://docs.docker.com/engine/installation/>`_, testing
Nipype is as easy as follows::

  cd path/to/nipype/
  docker build -f docker/nipype_test/Dockerfile_py27 -t nipype/nipype_test:py27
  docker run -it --rm -v /etc/localtime:/etc/localtime:ro \
                      -e FSL_COURSE_DATA="/root/examples/nipype-fsl_course_data" \
                      -v ~/examples:/root/examples:ro \
                      -v ~/scratch:/scratch \
                      -w /root/src/nipype \
                      nipype/nipype_test:py27 /usr/bin/run_nosetests.sh

For running nipype in Python 3.5::

  cd path/to/nipype/
  docker build -f docker/nipype_test/Dockerfile_py35 -t nipype/nipype_test:py35
  docker run -it --rm -v /etc/localtime:/etc/localtime:ro \
                      -e FSL_COURSE_DATA="/root/examples/nipype-fsl_course_data" \
                      -v ~/examples:/root/examples:ro \
                      -v ~/scratch:/scratch \
                      -w /root/src/nipype \
                      nipype/nipype_test:py35 /usr/bin/run_nosetests.sh
