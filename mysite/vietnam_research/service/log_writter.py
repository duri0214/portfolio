import inspect
import os
from pathlib import Path

from django.utils.timezone import now


def batch_is_done(number_of_records, log_file_name='result.log'):
    """
    「2023-02-03 Fri 11:26:53 xxxx.py is done.(141)」を出力

    Args:
        number_of_records: ログファイルに書き込みたい「処理した件数」
        log_file_name: ログファイル名を変更したい時に指定する
    """
    caller_dir = os.path.dirname(inspect.stack()[1].filename)
    caller_file_name = os.path.basename(inspect.stack()[1].filename)
    formatted_timestamp = now().strftime('%Y-%m-%d %a %H:%M:%S')
    formatted_info = f"{formatted_timestamp} {caller_file_name} is done.({number_of_records})\n"
    with open(Path(caller_dir) / f"{log_file_name}", mode='a') as f:
        f.write(formatted_info)
