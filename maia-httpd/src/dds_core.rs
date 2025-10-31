// src/dds_core.rs

//! DDS core device access via debugfs. 
use anyhow::{Context, Result};
use std::path::{Path, PathBuf};
use tokio::fs;

/// cf-ad9361-dds-core-lpc IIO debugfs device.
///
/// This struct represents the DDS core device and can be used to
/// write to its registers via the debugfs `direct_reg_access` file.
#[derive(Debug)]
pub struct DdsCore {
    debug_file_path: PathBuf,
}

impl DdsCore {
    /// Opens the cf-ad9361-dds-core-lpc device.
    ///
    /// This function finds the correct IIO device and constructs the path
    /// to its debugfs direct_reg_access file.
    pub async fn new() -> Result<Self> {
        let device_path = Self::find_iio_device()
            .await?
            .ok_or_else(|| anyhow::anyhow!("cf-ad9361-dds-core-lpc IIO device not found"))?;

        let device_name = device_path.file_name()
            .ok_or_else(|| anyhow::anyhow!("Could not get IIO device name"))?
            .to_str()
            .ok_or_else(|| anyhow::anyhow!("Device name is not valid UTF8"))?;
        
        // debugfs 경로를 만듭니다.
        let debug_file_path = Path::new("/sys/kernel/debug/iio/")
            .join(device_name)
            .join("direct_reg_access");

        Ok(DdsCore { debug_file_path })
    }

    /// Finds the IIO device path by its name.
    async fn find_iio_device() -> Result<Option<PathBuf>> {
        let mut entries = fs::read_dir("/sys/bus/iio/devices").await?;
        while let Some(entry) = entries.next_entry().await? {
            let mut path = entry.path();
            path.push("name");
            if path.exists() {
                let this_name = fs::read_to_string(&path).await?;
                if this_name.trim() == "cf-ad9361-dds-core-lpc" {
                    return Ok(Some(entry.path()));
                }
            }
        }
        Ok(None)
    }

    /// Writes a value to a specific register address.
    pub async fn write_register(&self, address: u32, value: u32) -> Result<()> {
        let content = format!("{address:#x} {value:#x}");
        fs::write(&self.debug_file_path, content.as_bytes())
            .await
            .with_context(|| format!("failed to write to {:?}", self.debug_file_path))?;
        Ok(())
    }
    
    /// Sets the I channel source (DDS_CHAN_CNTRL_7).
    pub async fn set_i_channel_source(&self, source: u32) -> Result<()> {
        self.write_register(0x80000418, source).await
    }
    
    /// Sets the Q channel source (DDS_CHAN_CNTRL_8).
    pub async fn set_q_channel_source(&self, source: u32) -> Result<()> {
        self.write_register(0x80000458, source).await
    }
}