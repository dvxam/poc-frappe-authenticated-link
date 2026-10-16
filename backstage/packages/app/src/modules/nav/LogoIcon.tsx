import { makeStyles } from '@material-ui/core';
import { vidiLogoDataUri } from './vidiLogo';

const useStyles = makeStyles({
  wrapper: {
    backgroundColor: 'white',
    borderRadius: 6,
    padding: 4,
    display: 'inline-flex',
  },
  img: {
    height: 24,
    width: 24,
    objectFit: 'contain',
    display: 'block',
  },
});

export const LogoIcon = () => {
  const classes = useStyles();
  return (
    <span className={classes.wrapper}>
      <img className={classes.img} src={vidiLogoDataUri} alt="Vidi" />
    </span>
  );
};
