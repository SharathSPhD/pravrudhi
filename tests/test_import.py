def test_engine_imports_kernel() -> None:
    import pravrudhi
    import pravrudhi_kernel

    assert pravrudhi.__version__ == "0.2.4"
    assert pravrudhi_kernel.__version__ == pravrudhi.KERNEL_VERSION
