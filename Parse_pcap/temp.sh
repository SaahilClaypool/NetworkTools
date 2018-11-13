rm *.csv; cargo run '.*' '../../Config/Validation/Results/80m_bbr_netem/'; python3 plot.py . tarta 80m_netem.png
rm *.csv; cargo run '.*' '../../Config/Validation/Results/80m_bbr_tbf/'; python3 plot.py . tarta 80m_tbf.png
rm *.csv; cargo run '.*' '../../Config/Validation/Results/80m_bbr_tbf_peak/'; python3 plot.py . tarta 80m_tbf_peak.png