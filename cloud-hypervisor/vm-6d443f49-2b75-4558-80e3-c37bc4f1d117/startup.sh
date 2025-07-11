#!/bin/bash
echo 'Cloud Hypervisor VM Starting...'
echo 'VM Configuration:'
echo '  CPUs: 1'
echo '  Memory: 512M'
echo '  Network: Available'
echo ''
echo 'Installing Python packages...'
pip install numpy pandas matplotlib seaborn scikit-learn jupyter ipython

# Custom startup script
echo "Data Science Cloud Hypervisor VM ready!"
python -c "import numpy, pandas, matplotlib; print('Libraries loaded successfully')"

echo 'Cloud Hypervisor VM ready!'
echo 'Type commands to interact with the VM'
