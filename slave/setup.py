import subprocess
import configparser
config = configparser.ConfigParser()
config.read("config.toml")
config.beanstalkd
subprocess.run(["ssh", "-t", "beanstalkd"])
https://github.com/beanstalkd/beanstalkd.git
