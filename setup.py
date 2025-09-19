from setuptools import setup, find_packages

setup(
    name="wazo-survey-plugin",
    version="0.1.0",
    description="Post-call survey IVR + transfer endpoint for wazo-calld",
    packages=find_packages(),
    include_package_data=True,
    install_requires=["Flask>=2.0.0", "requests>=2.25.0"],
    entry_points={
        "wazo_calld.plugins": [
            "wazo_survey = survey_plugin.plugin:Plugin",
        ],
    },
)
