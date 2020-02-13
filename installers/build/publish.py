'''
Upload artifacts to Github release
'''
import os
import glob
import requests
import uritemplate


tag = os.environ.get('CI_BRANCH')
github_api_user = os.environ.get('GITHUB_API_USER')
github_api_token = os.environ.get('GITHUB_API_TOKEN')
artifacts = glob.glob('/artifacts/conductor-%s*' % tag)
release_url = 'https://api.github.com/repos/AtomicConductor/conductor_client/releases/tags/%s' % tag


if not artifacts:
    print 'No artifacts found'
    exit(2)

release = requests.get(release_url)
if 200 != release.status_code:
    print 'No release found'
    exit(2)

responses = []
for artifact in artifacts:
    
    # Don't publish the unsigned installers
    if 'unsigned' in artifact:
        continue
    
    uri_template = uritemplate.URITemplate(release.json()['upload_url'])
    upload_url = uri_template.expand(name=os.path.basename(artifact))
    with open(artifact, 'rb') as fh:
        response = requests.post(upload_url,
                                 data=fh.read(),
                                 auth=(github_api_user, github_api_token),
                                 headers={'content-type': 'application/octet-stream'})
        responses.append(response)
        print response.json()

for response in responses:
    response.raise_for_status()
