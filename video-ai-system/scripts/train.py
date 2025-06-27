import argparse
import os
import subprocess
import sys
import torch
from mmcv import Config
from mmaction.apis import train_model, set_random_seed, init_recognizer
from mmaction.datasets import build_dataset

# Helper function to install requirements
def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def main():
    """
    Standalone training script for VideoMAE pre-training on SageMaker.
    This script is designed to be the entry point for a SageMaker training job.
    It takes hyperparameters and data paths as arguments, prepares the environment,
    and launches the MMAction2 training process.
    """
    parser = argparse.ArgumentParser(description='SageMaker VideoMAE Training')

    # --- SageMaker Environment Arguments ---
    parser.add_argument('--model-dir', type=str, default=os.environ.get('SM_MODEL_DIR', '/opt/ml/model'),
                        help='Directory to save the trained model.')
    parser.add_argument('--train', type=str, default=os.environ.get('SM_CHANNEL_TRAINING', '/opt/ml/input/data/training'),
                        help='Directory with training data.')
    parser.add_argument('--hosts', type=list, default=os.environ.get('SM_HOSTS', '["algo-1"]'),
                        help='List of hosts in the training cluster.')
    parser.add_argument('--current-host', type=str, default=os.environ.get('SM_CURRENT_HOST', 'algo-1'),
                        help='The current host in the training cluster.')
    parser.add_argument('--num-gpus', type=int, default=os.environ.get('SM_NUM_GPUS', 1),
                        help='Number of GPUs available on the current host.')

    # --- Hyperparameters ---
    parser.add_argument('--epochs', type=int, default=800, help='Total number of training epochs.')
    parser.add_argument('--lr', type=float, default=1.5e-4, help='Learning rate.')
    parser.add_argument('--batch_size', type=int, default=8, help='Batch size per GPU.')
    parser.add_argument('--warmup_epochs', type=int, default=40, help='Number of warmup epochs for the learning rate scheduler.')
    parser.add_argument('--seed', type=int, default=42, help='Random seed for reproducibility.')

    args = parser.parse_args()

    print("--- Environment Setup ---")
    # The SageMaker PyTorch container will install from requirements.txt in the source_dir.
    # We can also manually install mmaction2 if needed.
    # install('mmaction2')
    
    # --- Configuration ---
    # We will use a base configuration and override it with the provided arguments.
    # This assumes a base config file is present in the source directory.
    # For this example, we create the config dynamically like in the notebook.
    
    print("--- Creating MMAction2 Config ---")
    
    # Paths within the SageMaker container
    data_root = args.train
    work_dir = os.path.join(args.model_dir, 'work_dir')
    os.makedirs(work_dir, exist_ok=True)
    
    # For self-supervised learning, we just need a list of video files.
    # We assume the training channel contains video files directly.
    # A real-world scenario might have a more complex structure and require
    # creating an annotation file here.
    ann_file_train = os.path.join(data_root, 'annotations.txt')
    with open(ann_file_train, 'w') as f:
        for video_file in os.listdir(data_root):
            if video_file.endswith(('.mp4', '.webm')):
                # mmaction2 expects a placeholder label for pre-training
                f.write(f"{video_file} -1\n")

    config_content = f"""
_base_ = [
    './configs/_base_/models/videomae_vit-base-p16.py',
    './configs/_base_/default_runtime.py'
]

# model settings
model = dict(
    backbone=dict(drop_path_rate=0.1),
    neck=dict(type='VideoMAEPretrainNeck',
        embed_dims=768,
        patch_size=16,
        tube_size=2,
        decoder_embed_dims=384,
        decoder_depth=4,
        decoder_num_heads=6,
        mlp_ratio=4.,
        norm_pix_loss=True),
    head=dict(type='VideoMAEPretrainHead',
        norm_pix_loss=True,
        patch_size=16,
        tube_size=2))

# dataset settings
dataset_type = 'VideoDataset'
data_root = '{data_root}'
ann_file_train = '{ann_file_train}'

train_pipeline = [
    dict(type='DecordInit'),
    dict(type='SampleFrames', clip_len=16, frame_interval=4, num_clips=1),
    dict(type='DecordDecode'),
    dict(type='Resize', scale=(-1, 256)),
    dict(type='RandomResizedCrop', area_range=(0.5, 1.0)),
    dict(type='Resize', scale=(224, 224), keep_ratio=False),
    dict(type='Flip', flip_ratio=0.5),
    dict(type='FormatShape', input_format='NCTHW'),
    dict(type='MaskingGenerator', mask_window_size=(8, 7, 7), mask_ratio=0.75),
    dict(type='Collect', keys=['imgs', 'mask'], meta_keys=()),
    dict(type='ToTensor', keys=['imgs', 'mask'])]

data = dict(
    videos_per_gpu={args.batch_size}, 
    workers_per_gpu=4,
    train=dict(
        type=dataset_type,
        ann_file=ann_file_train,
        data_prefix=data_root,
        pipeline=train_pipeline))

# optimizer
optimizer = dict(
    type='AdamW',
    lr={args.lr},
    betas=(0.9, 0.95),
    weight_decay=0.05)

# learning policy
lr_config = dict(
    policy='CosineAnnealing',
    min_lr=0,
    warmup='linear',
    warmup_by_epoch=True,
    warmup_iters={args.warmup_epochs})

total_epochs = {args.epochs}

# runtime settings
work_dir = '{work_dir}'
log_config = dict(interval=50, hooks=[dict(type='TextLoggerHook'), dict(type='TensorboardLoggerHook')])

# enable mixed-precision training
fp16 = dict(loss_scale='dynamic')
"""
    
    config_path = './sagemaker_videomae_config.py'
    with open(config_path, 'w') as f:
        f.write(config_content)
        
    cfg = Config.fromfile(config_path)

    # --- Training ---
    print(f"--- Starting Training for {args.epochs} epochs ---")
    
    # Set seed for reproducibility
    if args.seed is not None:
        set_random_seed(args.seed, deterministic=True)
        cfg.seed = args.seed

    cfg.gpu_ids = range(args.num_gpus)
    
    datasets = [build_dataset(cfg.data.train)]
    
    train_model(
        model,
        datasets,
        cfg,
        distributed=len(args.hosts) > 1,
        validate=False, # No validation set in this pre-training example
        timestamp=None,
        meta=None
    )

    # --- Model Export ---
    print("--- Training Complete. Exporting model to ONNX. ---")
    
    final_checkpoint = os.path.join(work_dir, f'epoch_{args.epochs}.pth')
    
    # Ensure the checkpoint exists
    if not os.path.exists(final_checkpoint):
        print(f"Error: Checkpoint file not found at {final_checkpoint}")
        # Fallback to latest if final not found
        checkpoints = [f for f in os.listdir(work_dir) if f.endswith('.pth')]
        if not checkpoints:
            print("Error: No checkpoints found in work_dir.")
            return
        final_checkpoint = os.path.join(work_dir, sorted(checkpoints)[-1])
        print(f"Using latest checkpoint instead: {final_checkpoint}")

    # Build the model from the config and the final checkpoint
    model = init_recognizer(cfg, final_checkpoint, device='cpu')
    
    # We only export the encoder backbone
    encoder = model.backbone
    
    # Create a dummy input for tracing
    dummy_input = torch.randn(1, 3, 16, 224, 224)
    
    # Define the output path in the SageMaker model directory
    onnx_output_path = os.path.join(args.model_dir, 'model.onnx')
    
    torch.onnx.export(
        encoder,
        dummy_input,
        onnx_output_path,
        input_names=['input'],
        output_names=['output'],
        opset_version=11,
        dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}}
    )
    
    print(f"ONNX model successfully exported to: {onnx_output_path}")

if __name__ == '__main__':
    # To run mmaction2 tools, we need to be in a directory that can see the configs.
    # A better approach for production is to install mmaction2 as a package.
    # For this script, we assume it's run from a directory containing the 'configs' folder.
    # The SageMaker Estimator's `source_dir` will be the root. We might need to clone
    # mmaction2 inside the container or package it.
    
    # For simplicity, we assume the estimator is set up to handle this.
    # A common pattern is to have a shell script entrypoint that clones the repo.
    main()