import os
import time

import pytest
from selenium import webdriver
from selenium.webdriver.common.by import By

from microscopium.serve import run_server


@pytest.fixture
def driver(request):
    driver_ = webdriver.Firefox()

    def quit():
        driver_.quit()

    request.addfinalizer(quit)
    return driver_


@pytest.fixture()
def server():
    run_server('testdata/images/data.csv', port=5000)


def test_valid_credentials(driver):
    """Test that there is no server error upon startup."""
    # Currently works only if localhost is already running
    driver.get("http://localhost:5000/")
    time.sleep(5)  # bad style, fix this later
    title = driver.title
    assert title == "Bokeh microscopium app"


def test_google(driver):
    """A basic example to check our tests work."""
    driver.get("https://www.google.com/")
    time.sleep(5)  # bad style, fix this later
    title = driver.title
    assert title == "Google"


def test_pass():
    assert True
