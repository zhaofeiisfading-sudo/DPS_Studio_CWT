"""All-channel read-only observations. Synthetic-noise scoring is exploratory here."""

from pathlib import Path
from typing import Any

import numpy as np

from pdv_cwt.mapping import load_config
from pdv_cwt.readers import audit_file, read_channel
from pdv_cwt.safety import ROOT, checked_path, sha256

from .io import array_hash, output, write_csv, write_json
from .run import profile_key
from .scoring import METHODS, Bank, cwt, cwt_banks, score_response, stft_bank, support

PRIOR = ROOT / "artifacts/TASK-CWT-004/run_20261030_165336_eef69e3e/real"


def plots(
    directory: Path, title: str, time_s: Any, banks: dict[str, Bank], diagnostics: Any
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    fig, axes = plt.subplots(5, 1, figsize=(13, 12), sharex=True, layout="constrained")
    for ax, method in zip(axes, METHODS, strict=True):
        bank = banks[method]
        reference = max(float(np.median(bank.score)), np.finfo(float).tiny)
        db = 20 * np.log10(np.maximum(bank.score / reference, 1e-15))
        mesh = ax.pcolormesh(
            time_s * 1e6,
            bank.hz / 1e9,
            db,
            shading="nearest",
            vmin=-20,
            vmax=60,
            cmap="magma",
            rasterized=True,
        )
        ax.plot(time_s * 1e6, bank.predicted / 1e9, color="cyan", lw=0.5)
        ax.fill_between(time_s * 1e6, 0.1, 6, where=bank.edge, color="gray", alpha=0.25)
        ax.set_ylim(0.1, 6)
        ax.set_ylabel(f"{method}\nGHz")
        fig.colorbar(mesh, ax=ax, label="dB / record median (not SNR)")
    axes[-1].set_xlim(float(time_s[0] * 1e6), float(time_s[-1] * 1e6))
    axes[-1].set_xlabel("Original absolute time (us)")
    fig.suptitle(title + " | A2 exploratory; real noise/truth UNKNOWN")
    fig.savefig(output(directory / "spectral_support.png"), dpi=180)
    plt.close(fig)
    fig, axes = plt.subplots(3, 1, figsize=(13, 8), sharex=True, layout="constrained")
    for method in METHODS:
        bank = banks[method]
        median = np.median(bank.score, axis=0)
        axes[0].plot(time_s * 1e6, bank.peak / np.maximum(median, 1e-300), label=method)
        axes[1].plot(time_s * 1e6, diagnostics[f"{method}_reference_rank"], label=method)
        axes[2].plot(time_s * 1e6, bank.predicted / 1e9, lw=0.5, label=method)
    axes[0].set_ylabel("peak / band median")
    axes[0].set_yscale("log")
    axes[0].legend(ncol=5)
    axes[1].set_ylabel("A0-frequency local peak rank")
    axes[2].set_ylabel("Candidate GHz")
    axes[2].set_xlabel("Original absolute time (us)")
    fig.suptitle(title + " | descriptive; reference is not truth")
    fig.savefig(output(directory / "quality_diagnostics.png"), dpi=180)
    plt.close(fig)


def real_run(run: Path, profiles: dict[str, list[float]]) -> list[dict[str, Any]]:
    config = load_config(ROOT / "configs/real_batch.toml")
    summaries: list[dict[str, Any]] = []
    index = []
    for filename, mapping in config.mappings.items():
        path = checked_path(config.raw_root / filename, config.raw_root)
        audit = audit_file(path, mapping, config.max_input_bytes)
        if audit["status"] != "READY":
            raise ValueError(f"raw audit failed {filename}: {audit}")
        for channel in mapping.channels:
            directory = output(run / "real" / f"{path.stem}_{channel.name}" / "placeholder").parent
            signal = read_channel(
                path,
                mapping,
                channel,
                rows=audit["data_rows"],
                expected_sha256=audit["sha256_before"],
                max_reader_bytes=config.max_reader_bytes,
            )
            calibration_rate = min((40e9, 80e9), key=lambda f: abs(f - signal.sampling_rate_hz))
            if abs(calibration_rate / signal.sampling_rate_hz - 1) > 1e-6:
                raise ValueError("no preregistered sample-rate calibration reference")
            result, elapsed = cwt(signal)
            rms = np.asarray(profiles[profile_key(calibration_rate, "white")])
            banks = cwt_banks(result, rms)
            centers = banks["A0"].centers
            times = signal.time_s[centers]
            raw = np.abs(result.coefficients)
            native: dict[str, Any] = dict(time_s=signal.time_s)
            distance = np.minimum(
                np.arange(signal.time_s.size), np.arange(signal.time_s.size)[::-1]
            )
            native["bank_edge"] = distance < result.grid.support_radius_samples.max()
            for mode in METHODS[:3]:
                response = score_response(raw, result.grid.scales, mode, rms)
                selected = np.argmax(response, axis=0)
                native[f"{mode}_frequency_hz"] = result.grid.frequency_hz[selected]
                native[f"{mode}_peak"] = response[selected, np.arange(selected.size)]
                native[f"{mode}_selected_edge"] = (
                    distance < result.grid.support_radius_samples[selected]
                )
                native[f"{mode}_alias_risk"] = result.grid.alias_tail_fraction[selected] > 1e-6
                if mode != "A0":
                    del response
            prior_directory = PRIOR / directory.name
            with np.load(prior_directory / "cwt/native.npz") as prior:
                np.testing.assert_array_equal(native["time_s"], prior["time_s"])
                np.testing.assert_array_equal(native["A0_frequency_hz"], prior["frequency_hz"])
            del raw, result
            np.savez_compressed(output(directory / "native.npz"), **native)
            for mode, high in (("balanced", False), ("high_time", True)):
                banks[mode] = stft_bank(signal, high)
                with np.load(prior_directory / f"{mode}/native.npz") as prior:
                    np.testing.assert_array_equal(times, prior["time_s"])
                    np.testing.assert_array_equal(banks[mode].predicted, prior["frequency_hz"])
            interior = ~np.logical_or.reduce([b.edge for b in banks.values()])
            saved: dict[str, Any] = dict(sample_index=centers, time_s=times, interior=interior)
            diagnostic: dict[str, Any] = {}
            relative = times - signal.time_s[0]
            duration = signal.time_s[-1] - signal.time_s[0]
            windows = {"all_interior": interior}
            for ordinal, label in enumerate(("first_third", "middle_third", "last_third")):
                windows[label] = (
                    interior
                    & (relative >= ordinal * duration / 3)
                    & (relative < (ordinal + 1) * duration / 3)
                )
            for band, mask in (
                ("low_strong", banks["A0"].hz < 0.5e9),
                ("high_strong", banks["A0"].hz >= 2e9),
            ):
                energy = banks["A0"].score[mask].max(axis=0)
                windows[band] = interior & (energy >= np.quantile(energy[interior], 0.9))
            strongest_time = relative[np.argmax(np.where(interior, banks["A0"].peak, -np.inf))]
            windows["strongest_neighborhood"] = interior & (
                np.abs(relative - strongest_time) <= 20e-9
            )
            changes = np.abs(np.diff(banks["A0"].predicted))
            change_time = relative[1:][
                np.argmax(np.where(interior[1:] & interior[:-1], changes, -1))
            ]
            windows["largest_change_neighborhood"] = interior & (
                np.abs(relative - change_time) <= 20e-9
            )
            if filename == "ch3.csv":
                windows["ch3_weak_observation"] = (
                    interior & (relative >= 1.08e-6) & (relative < 1.3e-6)
                )
                windows["ch3_background_observation"] = interior & (relative < 1e-6)
            if filename == "20260607.csv":
                windows["prior_low_band"] = interior & (relative >= 0.75e-6) & (relative < 1.25e-6)
            for name, mask in windows.items():
                saved[f"window_{name}"] = mask
            for mode, b in banks.items():
                sup = support(b.score, b.hz, banks["A0"].predicted)
                saved[f"{mode}_frequency_grid_hz"] = b.hz
                saved[f"{mode}_response"] = b.score
                saved[f"{mode}_prediction"] = b.predicted
                saved[f"{mode}_peak"] = b.peak
                saved[f"{mode}_reference_rank"] = sup["rank"]
                diagnostic[f"{mode}_reference_rank"] = sup["rank"]
                for name, mask in windows.items():
                    pairs = mask[1:] & mask[:-1]
                    summaries.append(
                        dict(
                            file=filename,
                            channel=channel.name,
                            method=mode,
                            window=name,
                            frames=int(mask.sum()),
                            candidate_modification_rate=float(
                                np.mean(b.predicted[mask] != banks["A0"].predicted[mask])
                            ),
                            median_abs_difference_from_A0_hz=float(
                                np.median(np.abs(b.predicted[mask] - banks["A0"].predicted[mask]))
                            ),
                            jump_rate=float(np.mean((np.abs(np.diff(b.predicted)) > 0.5e9)[pairs]))
                            if pairs.any()
                            else None,
                            frequency_median_hz=float(np.median(b.predicted[mask])),
                            response_median=float(np.median(b.peak[mask])),
                            A0_reference_peak_presence=float(np.mean(sup["presence"][mask])),
                            A0_reference_top5=float(np.mean(sup["top5"][mask])),
                            quality="UNKNOWN",
                            truth="UNKNOWN",
                            exploratory=True,
                            A2_calibration=(
                                "EXPLORATORY synthetic white profile; real noise UNKNOWN"
                            ),
                        )
                    )
            np.savez_compressed(output(directory / "common_spectral_support.npz"), **saved)
            plots(directory, f"{filename}/{channel.name}", times, banks, diagnostic)
            record = dict(
                file=filename,
                channel=channel.name,
                samples=signal.time_s.size,
                original_t0_s=float(signal.time_s[0]),
                original_tlast_s=float(signal.time_s[-1]),
                time_sha256=array_hash(signal.time_s),
                voltage_sha256=array_hash(signal.voltage_v),
                raw_sha256_before=audit["sha256_before"],
                raw_sha256_after=sha256(path),
                cwt_s=elapsed,
                native_candidates=signal.time_s.size,
                native_exact_prior_A0=True,
                stft_exact_prior=True,
                directory=directory.relative_to(run).as_posix(),
                A2_status="EXPLORATORY; not calibrated real measurement",
                truth="UNKNOWN",
                velocity="NOT COMPUTED",
                display="common actual frame centers",
            )
            if record["raw_sha256_after"] != record["raw_sha256_before"]:
                raise ValueError("raw changed during real analysis")
            write_json(directory / "metadata.json", record)
            index.append(record)
            print(f"real {len(index)}/14 {filename}/{channel.name}", flush=True)
    assert len(index) == 14
    write_csv(run / "real_diagnostics.csv", summaries)
    write_json(run / "real_channel_index.json", index)
    return index
