from typing import List

import time
import glob
import os
import subprocess


__all__ = 'ControlPoint',


class DockerCommands:
    @staticmethod
    def make(commands: List[str]) -> None:
        """
        Looks like:
            make YOUR_COMMANDS
        """
        commands = [f"make {' '.join(commands)}"]
        print('COMMANDS `make`: ', commands, '\n')
        subprocess.call(commands, shell=True)

    @staticmethod
    def docker(commands: List[str]) -> None:
        """
        Looks like:
            docker YOUR_COMMANDS
        """
        commands = [f"docker {' '.join(commands)}"]
        print('COMMANDS `docker`: ', commands, '\n')
        subprocess.call(commands, shell=True)

    @staticmethod
    def docker_compose(commands: List[str]) -> None:
        """
        Looks like:
            docker-compose YOUR_COMMANDS
        """
        commands = list(map(lambda x: f'docker-compose {x} ', commands))
        print('COMMANDS `docker_compose`: ', commands, '\n')
        subprocess.call(commands, shell=True)

    def backend_run(self, commands: List[str]) -> None:
        """
        Looks like:
            docker-compose run --rm django YOUR_COMMANDS
        """
        go_backend = 'run --rm django'
        commands = [f"{go_backend} {' '.join(commands)}"]
        self.docker_compose(commands)

    def manage_py(self, commands: List[str]) -> None:
        """
        Looks like:
            docker-compose run --rm django python manage.py YOUR_COMMANDS
        """
        manage_py = 'python manage.py'
        commands = [f"{manage_py} {' '.join(commands)}"]
        self.backend_run(commands)


class ControlPoint(DockerCommands):
    """ Run from project root via `python3 my_scripts/control_point.py` """

    def __init__(self, *args, **kwargs):
        self.db_container_name = 'postgres'
        self.backend_container_name = 'django'
        self.pipeline = [
            # 'delete_migrations',
            'kill_all_containers',
            # 'clean_space',
            'rebuild_db',
            # 'install_requirements',
            # 'install_requirements_local',
            # 'makemigrations',
            'migrate',
            'run_fixtures',
            # 'run_tests',
            # 'create_superuser',
            # 'load_last_dump',
            'start_project'
        ]

    def run(self) -> None:
        pipeline_repr = '\n - ' + '\n - '.join(self.pipeline)
        # TODO: colorize
        answer = input(
            'Are you sure you want to continue?\n'
            'to continue - y\n\n'
            f'Pipeline: {pipeline_repr}\n\n'
            'to cancel - n or leave empty\n\n'
            'Answer: '
        )
        if answer.lower() in ('y', 'yes'):
            for method in self.pipeline:
                getattr(self, method)()

    def makemigrations(self) -> None:
        # TODO: parse apps and find out ordering
        apps = [
            # 'companies',
            # 'profiles',
            # 'clients',
            # 'employees',
            # 'integrations',
            # 'statistics',
            # 'warehouses',
            # 'orders',
            # 'finance',
            # 'core',
            # 'landing',
            # 'pages',
            # 'tariff_plans',
            # 'invoices',
        ]

        commands = [f"makemigrations {' '.join(apps)}"]
        self.manage_py(commands)

    @staticmethod
    def delete_migrations() -> None:
        path = f'{os.getcwd()}/packages/django/server/apps'
        dirs = os.listdir(path)
        for dr in dirs:
            try:
                deep_path = f'{path}/{dr}'
                deep_dirs = os.listdir(deep_path)
                if 'migrations' in deep_dirs:
                    print('\n')
                    migrations = os.listdir(f'{deep_path}/migrations')
                    for file in migrations:
                        if file not in ('__init__.py', '__pycache__'):
                            os.remove(f'{deep_path}/migrations/{file}')
                            print(f'removed {deep_path}/migrations/{file}')
                    print('\n')
            except NotADirectoryError:
                pass

    def kill_all_containers(self) -> None:
        self.docker(['kill $(docker ps -q)'])

    def rebuild_db(self) -> None:
        start_container = [f'docker-compose start {self.db_container_name}']

        recreate_db = [
            f'docker-compose exec {self.db_container_name} '
            f'psql --user postgres '
            f'-c "drop database database;" -c "create database database;"'
        ]

        commands = [start_container, recreate_db]
        for c in commands:
            result = subprocess.run(c, shell=True, stdout=subprocess.PIPE)
            message = result.stdout.decode('utf-8').strip()

            if message != 'psql: FATAL:  the database system is starting up':
                print(message)
            else:
                print('\nError!\nReloading Docker...\n')
                cmd = ['killall Docker && open /Applications/Docker.app']
                subprocess.call(cmd, shell=True)

                while True:
                    time.sleep(5)
                    result = subprocess.run(
                        ['docker ps'], shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    error_message = result.stderr.decode('utf-8').strip()
                    message = result.stdout.decode('utf-8').strip()
                    if message and not error_message:
                        break

                for cmd in (start_container, c):
                    subprocess.run(cmd, shell=True)

    def install_requirements(self) -> None:
        self.docker_compose(['build django celery'])

    def install_requirements_local(self) -> None:
        subprocess.call([
            'cd packages/django/server '
            '&& source .venv/bin/activate '
            '&& pip install -r requirements.base.txt'
        ], shell=True)

    def migrate(self) -> None:
        self.manage_py(['migrate'])

    def run_fixtures(self) -> None:
        fixtures = self.parse_fixtures()
        self.manage_py([f"loaddata {' '.join(fixtures)}"])

    @staticmethod
    def parse_fixtures() -> List[str]:
        """
        Parsing all project fixtures
        Requirements:
            1. Fixture should be in "fixtures" dir
            2. Fixture should have .json extension
        """
        fixture_files = list()
        for dir_path, dir_names, file_names in os.walk('.'):
            if 'fixtures' in dir_names:
                fixtures_dir = os.path.join(dir_path, 'fixtures')
                for filename in os.listdir(fixtures_dir):
                    if filename.endswith('.json'):
                        fixture_files.append(filename)
        print('FOUND FIXTURES: ', fixture_files, '\n')
        return fixture_files

    def run_tests(self) -> None:
        self.manage_py(['test'])

    def create_superuser(self) -> None:
        self.manage_py(['createsuperuser'])

    def load_last_dump(self) -> None:
        self.docker_compose([f'start {self.db_container_name}'])

        dump = self.get_last_dump()
        if dump is not None:
            answer = input((
                'Load this dump?\n'
                'to continue - y\n'
                'to cancel - n or leave empty\n\n'
                'Answer: '
            ))

            if answer.lower() in ('y', 'yes'):
                self.backend_run([f'psql -U postgres -d database < {dump}'])

    @staticmethod
    def get_last_dump() -> str:
        path = f'{os.getcwd()}/dumps/*'
        files = glob.glob(path)

        if files:
            latest_dump = max(files, key=os.path.getctime)

            print(f'gonna load this:\n{latest_dump}')
            print('{:2}{}'.format('', '– ' * 15))

            return latest_dump
        else:
            print('\n{:2}{}\n'.format('', f'There is no dumps to load.'))

    def start_project(self) -> None:
        self.make(['application-dev'])

    @staticmethod
    def clean_space() -> None:
        subprocess.call([
            'docker container rm $(docker container ls -aq) '
            'docker rmi -f $(docker images -q) '
            'docker volume prune -f '
            '&& docker builder prune -f '
            '&& docker network prune -f '
        ], shell=True)


if __name__ == '__main__':
    ControlPoint().run()
