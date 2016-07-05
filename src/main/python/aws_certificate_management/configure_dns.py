from __future__ import print_function, absolute_import, division

import os
import re
from cfn_sphere import StackActionHandler
from cfn_sphere.stack_configuration import Config

import boto3

DNS_STACK_NAME_POSTFIX = "-ses-dns-records"
BUCKET_STACK_NAME_POSTFIX = "-email-bucket"


def prepare_domain(domain):
    # Stack names in CFN-sphere may not contain anything but letters,
    # numbers and "-".
    return re.sub("[^-a-zA-Z0-9]", "", domain)


def get_dns_stack_name(domain):
    return prepare_domain(domain) + DNS_STACK_NAME_POSTFIX


def get_bucket_stack_name(domain):
    return prepare_domain(domain) + BUCKET_STACK_NAME_POSTFIX


def get_stack_action_handler(domain, region, verification_token=None, dkim_tokens=None):
    ses_dns_template = "{0}/../../../../src/main/cfn/templates/recordset.json"
    ses_dns_template = ses_dns_template.format(os.path.abspath(os.path.dirname(__file__)))
    verification_token = verification_token or ""
    dkim_tokens = dkim_tokens or ["", "", ""]

    mail_bucket_template = "{0}/../../../../src/main/cfn/templates/ses-email-receiving-bucket.json"
    mail_bucket_template = mail_bucket_template.format(os.path.abspath(os.path.dirname(__file__)))

    return StackActionHandler(config=Config(config_dict={
        'region': region,
        'stacks': {
            get_dns_stack_name(domain): {
                'template-url': ses_dns_template,
                'parameters': {
                    'dnsBaseName': domain + ".",
                    'dkimOne': dkim_tokens[0],
                    'dkimTwo': dkim_tokens[1],
                    'dkimThree': dkim_tokens[2],
                    'verifyTxt': verification_token
                }
            },
            get_bucket_stack_name(domain): {
                'template-url': mail_bucket_template,
            }
        }
    }))


def normalize_domain(domain):
    if domain.startswith("*."):
        return domain[2:]
    return domain


def create_ses_dns_records(domain, region='eu-west-1'):
    domain = normalize_domain(domain)
    ses = boto3.client('ses', region_name=region)
    domain_identity = ses.verify_domain_identity(Domain=domain)
    verification_token = domain_identity['VerificationToken']
    dkim_tokens = ses.verify_domain_dkim(Domain=domain)['DkimTokens']

    stack_handler = get_stack_action_handler(domain, region, verification_token, dkim_tokens)
    stack_handler.create_or_update_stacks()

    return stack_handler.cfn.get_stack_outputs()[get_bucket_stack_name(domain)]['bucketName']


def delete_ses_dns_records(domain, region='eu-west-1'):
    domain = normalize_domain(domain)
    get_stack_action_handler(domain, region).delete_stacks()
