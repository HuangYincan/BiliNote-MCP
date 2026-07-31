def is_cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except ImportError:
        return False
def is_torch_installed() -> bool:
    try:
        import torch
        return True
    except ImportError:
        return False
