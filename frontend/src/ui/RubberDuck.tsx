import {SvgIcon, type SvgIconProps} from '@mui/material';

/** Ducky, Team Rubber Ducky's helper mascot. Fixed colours so it stays a duck in any theme. */
export default function RubberDuck({title = 'Ducky the rubber duck', ...props}: SvgIconProps & {title?: string}) {
  return (
    <SvgIcon viewBox="0 0 48 48" titleAccess={title} {...props} sx={{fontSize: 36, ...props.sx}}>
      <ellipse cx="22" cy="33" rx="16" ry="11" fill="#ffc933" />
      <path d="M34 30c3-1 5-4 5-8 0-6-5-10-11-10s-10 4-10 10c0 3 2 6 5 8z" fill="#ffc933" />
      <path d="M12 31c4 5 14 6 20 1-3 6-14 8-20-1z" fill="#f0a500" />
      <path d="M38 19l8 2-8 4z" fill="#f46800" />
      <circle cx="31" cy="19" r="2.2" fill="#1b1750" />
      <circle cx="31.7" cy="18.3" r=".7" fill="#ffffff" />
      <path d="M8 27c3-3 8-3 11 1-4 3-9 3-11-1z" fill="#f0a500" />
    </SvgIcon>
  );
}
