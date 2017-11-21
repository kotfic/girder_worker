import os

from girder.api import access
from girder.api.describe import Description, describeRoute
from girder.api.rest import Resource, filtermodel
from girder.utility.model_importer import ModelImporter

from girder.plugins.worker import utils
from girder.plugins.worker.constants import PluginSettings

from girder_worker.docker.tasks import docker_run
from girder_worker.docker.transform import (
    StdOut,
    NamedOutputPipe,
    NamedInputPipe,
    Connect,
    GirderFileIdToStream,
    FilePath,
    GirderUploadFilePathToItem,
    Volume,
    ProgressPipe,
    GirderFileIdToVolume,
)



TEST_IMAGE = 'girder/girder_worker_test:latest'


class DockerTestEndpoints(Resource):
    def __init__(self):
        super(DockerTestEndpoints, self).__init__()
        self.route('POST', ('test_docker_run', ),
                   self.test_docker_run)
        self.route('POST', ('test_docker_run_mount_volume', ),
                   self.test_docker_run_mount_volume)
        self.route('POST', ('test_docker_run_named_pipe_output', ),
                   self.test_docker_run_named_pipe_output)
        self.route('POST', ('test_docker_run_girder_file_to_named_pipe', ),
                   self.test_docker_run_girder_file_to_named_pipe)
        self.route('POST', ('test_docker_run_file_upload_to_item', ),
                   self.test_docker_run_file_upload_to_item)
        self.route('POST', ('test_docker_run_girder_file_to_named_pipe_on_temp_vol', ),
                   self.test_docker_run_girder_file_to_named_pipe_on_temp_vol)
        self.route('POST', ('test_docker_run_mount_idiomatic_volume', ),
                   self.test_docker_run_mount_idiomatic_volume)
        self.route('POST', ('test_docker_run_progress_pipe', ),
                   self.test_docker_run_progress_pipe)
        self.route('POST', ('test_docker_run_girder_file_to_volume', ),
                   self.test_docker_run_girder_file_to_volume)

    @access.token
    @filtermodel(model='job', plugin='jobs')
    @describeRoute(
        Description('Test basic docker_run.'))
    def test_docker_run(self, params):
        result = docker_run.delay(TEST_IMAGE, pull_image=True, container_args=['stdio', '-m', 'hello docker!'],
            remove_container=True)

        return result.job

    @access.token
    @filtermodel(model='job', plugin='jobs')
    @describeRoute(
        Description('Test mounting a volume.'))
    def test_docker_run_mount_volume(self, params):
        fixture_dir = params.get('fixtureDir')
        filename = 'read.txt'
        mount_dir = '/mnt/test'
        mount_path = os.path.join(mount_dir, filename)
        volumes = {
            fixture_dir: {
                'bind': mount_dir,
                'mode': 'ro'
            }
        }
        result = docker_run.delay(TEST_IMAGE, pull_image=True, container_args=['volume', '-p', mount_path],
            remove_container=True, volumes=volumes)

        return result.job

    @access.token
    @filtermodel(model='job', plugin='jobs')
    @describeRoute(
        Description('Test named pipe output.'))
    def test_docker_run_named_pipe_output(self, params):
        tmp_dir = params.get('tmpDir')
        message = params.get('message')
        mount_dir = '/mnt/girder_worker/data'
        pipe_name = 'output_pipe'

        volumes = {
            tmp_dir: {
                'bind': mount_dir,
                'mode': 'rw'
            }
        }

        connect = Connect(NamedOutputPipe(pipe_name, mount_dir, tmp_dir), StdOut())

        result = docker_run.delay(TEST_IMAGE, pull_image=True,
            container_args=['output_pipe', '-p', connect, '-m', message],
            remove_container=True, volumes=volumes)

        return result.job


    @access.token
    @filtermodel(model='job', plugin='jobs')
    @describeRoute(
        Description('Test downloading file using named pipe.'))
    def test_docker_run_girder_file_to_named_pipe(self, params):
        tmp_dir = params.get('tmpDir')
        file_id = params.get('fileId')
        mount_dir = '/mnt/girder_worker/data'
        pipe_name = 'input_pipe'

        volumes = {
            tmp_dir: {
                'bind': mount_dir,
                'mode': 'rw'
            }
        }

        connect = Connect(GirderFileIdToStream(file_id), NamedInputPipe(pipe_name, mount_dir, tmp_dir))

        result = docker_run.delay(TEST_IMAGE, pull_image=True, container_args=['input_pipe', '-p', connect],
            remove_container=True, volumes=volumes)


        return result.job

    @access.token
    @filtermodel(model='job', plugin='jobs')
    @describeRoute(
        Description('Test uploading output file to item.'))
    def test_docker_run_file_upload_to_item(self, params):
        item_id = params.get('itemId')
        contents = params.get('contents')

        filepath = FilePath('test_file')

        result = docker_run.delay(
            TEST_IMAGE, pull_image=True,
            container_args=['output_pipe', '-p', filepath, '-m', contents],
            remove_container=True, girder_result_hooks=[GirderUploadFilePathToItem(filepath, item_id)])

        return result.job

    @access.token
    @filtermodel(model='job', plugin='jobs')
    @describeRoute(
        Description('Test downloading file using named pipe.'))
    def test_docker_run_girder_file_to_named_pipe_on_temp_vol(self, params):
        """
        This is a simplified version of test_docker_run_girder_file_to_named_pipe
        it uses the TemporaryVolume, rather than having to setup the volumes
        'manually', this is the approach we should encourage.
        """
        file_id = params.get('fileId')
        pipe_name = 'input_pipe'

        connect = Connect(GirderFileIdToStream(file_id), NamedInputPipe(pipe_name))

        result = docker_run.delay(TEST_IMAGE, pull_image=True, container_args=['input_pipe', '-p', connect],
            remove_container=True)

        return result.job

    @access.token
    @filtermodel(model='job', plugin='jobs')
    @describeRoute(
        Description('Test idiomatic volume.'))
    def test_docker_run_mount_idiomatic_volume(self, params):
        fixture_dir = params.get('fixtureDir')
        filename = 'read.txt'
        mount_dir = '/mnt/test'
        mount_path = os.path.join(mount_dir, filename)
        volume = Volume(fixture_dir, mount_path, 'ro')
        filepath = FilePath(filename, volume)

        result = docker_run.delay(TEST_IMAGE, pull_image=True, container_args=['volume', '-p', filepath],
            remove_container=True, volumes=[volume])

        return result.job

    @access.token
    @filtermodel(model='job', plugin='jobs')
    @describeRoute(
        Description('Test progress pipe.'))
    def test_docker_run_progress_pipe(self, params):
        progressions = params.get('progressions')
        progress_pipe = ProgressPipe()

        result = docker_run.delay(
            TEST_IMAGE, pull_image=True,
            container_args=['progress', '-p', progress_pipe, '--progressions', progressions],
            remove_container=True)

        return result.job

    @access.token
    @filtermodel(model='job', plugin='jobs')
    @describeRoute(
        Description('Test download to volume.'))
    def test_docker_run_girder_file_to_volume(self, params):
        file_id = params.get('fileId')

        result = docker_run.delay(
            TEST_IMAGE, pull_image=True,
            container_args=['read_write', '-i', GirderFileIdToVolume(file_id),
                            '-o', Connect(NamedOutputPipe('out'), StdOut())],
            remove_container=True)

        return result.job
