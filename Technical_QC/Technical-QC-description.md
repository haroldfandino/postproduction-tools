# Description

I need a script to automate the technical QC for videos.

I'll provide a markdown called specifications.md with the expected specifications of the videos.

Like this:

- [ ] File Type: MOV
- [ ] Video Codec: ProRes 422
- [ ] Resolution: 1920 X 1080
- [ ] Frame rate: 23.976
- [ ] Duration: 00:00:30:00 or 30 seconds
- [ ] Color Space: Rec. 709
- [ ] Audio Codec: Uncompressed PCM
- [ ] Channels: 2 Stereo
- [ ] Sample Rate: 48 kHz
- [ ] Loudness: ⁓24 LKFS

or this:

- [ ] File Type: MP4
- [ ] Video Codec: H.264
- [ ] Resolution: 1920 X 1080
- [ ] Frame rate: 23.976
- [ ] Duration: 00:00:30:00 or 30 seconds
- [ ] Total bitrate: ⁓25 mbps
- [ ] Color Space: Rec. 709
- [ ] Audio Codec: Compressed
- [ ] Channels: 2 Stereo
- [ ] Sample Rate: 48 kHz
- [ ] Loudness: ⁓14 LKFS

The script will find in its current folder location, without asking for a folder location several videos with a naming convention like this:

[Client]_[ProjectDescription]_[ProjectType]_[Duration]_[Horizontal or Vertical]_[HD or 4K]_[Type of audio: Social or TV]_[Codec: H264 or ProRes].[Extension: mp4 or mov]

Filmkraft videos can also use this shorter naming convention, with horizontal orientation assumed:

[Client]_[ProjectDescription]_[Duration]_[HD or 4K]_[Type of audio: Social or TV]_[Codec: H264 or ProRes].[Extension: mp4 or mov]

The duration tag can be a numeric target such as 6, 15, or 30. It can also be
Longform. When the duration tag is Longform, the script should not check duration
against a target; it should only show the measured duration in the QC report.

This is an example:

- Carve_Feb2026_Signature_15_Horizontal_HD_SOCIAL_H264.mp4
- Carve_Feb2026_Signature_15_Horizontal_HD_SOCIAL_Prores.mov
- Carve_Feb2026_Signature_30_Horizontal_HD_SOCIAL_H264.mp4
- Carve_Feb2026_Signature_30_Horizontal_HD_SOCIAL_Prores.mov
- Carve_Feb2026_Signature_15_Vertical_HD_SOCIAL_H264.mp4
- Carve_Feb2026_Signature_15_Vertical_HD_SOCIAL_Prores.mov
- Carve_Feb2026_Signature_30_Vertical_HD_SOCIAL_H264.mp4
- Carve_Feb2026_Signature_30_Vertical_HD_SOCIAL_Prores.mov
- Mixbook_StoryModeLaunch_15_4K_SOCIAL_H264.mp4
- Mustela_DermatologistStories_BabyDiaperRash_Longform_4K_TV_Prores.mov
- Mustela_DermatologistStories_BabyDiaperRash_Longform_HD_TV_H264.mp4

The script needs to create profiles in the specifications.md to address the variations provided within the naming convention. For example:

For this

Carve_Feb2026_Signature_15_Horizontal_HD_SOCIAL_H264.mp4

- [ ] File Type: MP4
- [ ] Video Codec: H.264
- [ ] Resolution: 1920 X 1080
- [ ] Frame rate: 23.976
- [ ] Duration: 00:00:15:00 or 15 seconds
- [ ] Total bitrate: ⁓25 mbps
- [ ] Color Space: Rec. 709
- [ ] Audio Codec: Compressed
- [ ] Channels: 2 Stereo
- [ ] Sample Rate: 48 kHz
- [ ] Loudness: ⁓14 LKFS

or 

Carve_Feb2026_Signature_30_Horizontal_4K_TV_Prores.mov

- [ ] File Type: MOV
- [ ] Video Codec: ProRes 422
- [ ] Resolution: 3840 X 2160
- [ ] Frame rate: 23.976
- [ ] Duration: 00:00:30:00 or 30 seconds
- [ ] Color Space: Rec. 709
- [ ] Audio Codec: Uncompressed PCM
- [ ] Channels: 2 Stereo
- [ ] Sample Rate: 48 kHz
- [ ] Loudness: ⁓24 LKFS

or Carve_Feb2026_Signature_15_Vertical_HD_SOCIAL_H264.mp4

- [ ] File Type: MP4
- [ ] Video Codec: H.264
- [ ] Resolution: 1080 X 1920
- [ ] Frame rate: 23.976
- [ ] Duration: 00:00:15:00 or 15 seconds
- [ ] Total bitrate: ⁓25 mbps
- [ ] Color Space: Rec. 709
- [ ] Audio Codec: Compressed
- [ ] Channels: 2 Stereo
- [ ] Sample Rate: 48 kHz
- [ ] Loudness: ⁓14 LKFS

Once the markdown is updated, the script starts a performing the test an exports a markdown file for every video in the folder checking what part passed and what part didn't.

A few notes:

- Videos with **social audio** should have a loudness of ⁓14 LKFS and videos with **tv audio** ⁓24 LKFS.
- Vertical videos will have a resolution of 1080 X 1920.
- 4K MP4 videos are expected to have a bitrate of ⁓75 mbps and HD videos ⁓25 mbps.
