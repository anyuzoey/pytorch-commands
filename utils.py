import os
import glob
import torch
import shutil


class AverageMeter:
    """Computes and stores the average and current value"""
    def __init__(self):
        self.reset()

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        self.avg = self.sum / self.count


def get_outdir(path, *paths, inc=False):
    outdir = os.path.join(path, *paths)
    if not os.path.exists(outdir):
        os.makedirs(outdir)
    elif inc:
        count = 1
        outdir_inc = outdir + '-' + str(count)
        while os.path.exists(outdir_inc):
            count = count + 1
            outdir_inc = outdir + '-' + str(count)
            assert count < 100
        outdir = outdir_inc
        os.makedirs(outdir)
    return outdir


class CheckpointSaver:
    def __init__(
            self,
            checkpoint_prefix='checkpoint',
            recovery_prefix='recovery',
            checkpoint_dir='',
            recovery_dir='',
            max_history=10):

        self.checkpoint_files = []
        self.best_metric = None
        self.worst_metric = None
        self.max_history = max_history
        assert self.max_history >= 1
        self.curr_recovery_file = ''
        self.last_recovery_file = ''
        self.checkpoint_dir = checkpoint_dir
        self.recovery_dir = recovery_dir
        self.save_prefix = checkpoint_prefix
        self.recovery_prefix = recovery_prefix
        self.extension = '.pth.tar'

    def save_checkpoint(self, state, epoch, metric=None):
        worst_metric = self.checkpoint_files[-1] if self.checkpoint_files else None
        if len(self.checkpoint_files) < self.max_history or metric < worst_metric[1]:
            if len(self.checkpoint_files) >= self.max_history:
                self._cleanup_checkpoints(1)

            filename = '-'.join([self.save_prefix, str(epoch)]) + self.extension
            save_path = os.path.join(self.checkpoint_dir, filename)
            if metric is not None:
                state['metric'] = metric
            torch.save(state, save_path)
            self.checkpoint_files.append((save_path, metric))
            self.checkpoint_files = sorted(self.checkpoint_files, key=lambda x: x[1])

            print("Current checkpoints:")
            for c in self.checkpoint_files:
                print(c)

            if metric is not None and (self.best_metric is None or metric < self.best_metric[1]):
                self.best_metric = (epoch, metric)
                shutil.copyfile(save_path, os.path.join(self.checkpoint_dir, 'model_best' + self.extension))
        return None, None if self.best_metric is None else self.best_metric

    def _cleanup_checkpoints(self, trim=0):
        trim = min(len(self.checkpoint_files), trim)
        delete_index = self.max_history - trim
        if delete_index <= 0 or len(self.checkpoint_files) <= delete_index:
            return
        to_delete = self.checkpoint_files[delete_index:]
        for d in to_delete:
            try:
                print('Cleaning checkpoint: ', d)
                os.remove(d[0])
            except Exception as e:
                print('Exception (%s) while deleting checkpoint' % str(e))
        self.checkpoint_files = self.checkpoint_files[:delete_index]

    def save_recovery(self, state, epoch, batch_idx):
        filename = '-'.join([self.recovery_prefix, str(epoch), str(batch_idx)]) + self.extension
        save_path = os.path.join(self.recovery_dir, filename)
        torch.save(state, save_path)
        if os.path.exists(self.last_recovery_file):
            try:
                print('Cleaning recovery', self.last_recovery_file)
                os.remove(self.last_recovery_file)
            except Exception as e:
                print("Exception (%s) while removing %s" % (str(e), self.last_recovery_file))
        self.last_recovery_file = self.curr_recovery_file
        self.curr_recovery_file = save_path

    def find_recovery(self):
        recovery_path = os.path.join(self.recovery_dir, self.recovery_prefix)
        files = glob.glob(recovery_path + '*' + self.extension)
        files = sorted(files)
        if len(files):
            return files[0]
        else:
            return ''


def accuracy(output, target, topk=(1,)):
    """Computes the precision@k for the specified values of k"""
    maxk = max(topk)
    batch_size = target.size(0)

    _, pred = output.topk(maxk, 1, True, True)
    pred = pred.t()
    correct = pred.eq(target.view(1, -1).expand_as(pred))

    res = []
    for k in topk:
        correct_k = correct[:k].view(-1).float().sum(0)
        res.append(correct_k.mul_(100.0 / batch_size))
    return res